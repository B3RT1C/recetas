"""Personal shopping lists (not tied to any supermarket).

Quantities are stored in the canonical unit from `units.canonical` (g, ml or a count unit), so
the same ingredient coming from several recipes adds up; they are rounded only for display.
Prices are orientative: recipe ingredient prices (currently 'estimado') scaled to the servings,
or the price cache for manual items. Each list can hide them.
"""
from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import quote

from ..db import Database, now
from . import units as U

ESTADOS = ("pendiente", "ya_lo_tengo", "comprado")
CATEGORY_HINTS: list[tuple[str, str]] = [
    ("Fruta y verdura", r"cebolla|ajo|tomate|pimiento|patata|zanahoria|calabac|berenjena|lechuga|espinaca|puerro|"
                        r"limon|lima|naranja|manzana|platano|aguacate|perejil|cilantro|albahaca|champi|seta|pepino|"
                        r"brocoli|coliflor|judia verde|apio|jengibre|fresa|fruta|verdura|cebollino|hierbabuena|menta|boniato|calabaza"),
    ("Carne", r"pollo|ternera|cerdo|carne|bacon|beicon|jamon|chorizo|salchicha|pavo|cordero|lomo|costilla|pechuga|muslo|panceta|morcilla"),
    ("Pescado y marisco", r"salmon|atun|merluza|bacalao|gamba|langostino|mejillon|calamar|sepia|pulpo|pescado|anchoa|sardina|bonito"),
    ("Lácteos y huevos", r"huevo|yema|clara|leche|nata|queso|yogur|mantequilla|mozzarella|parmesano|burrata|requeson|kefir"),
    ("Panadería y cereales", r"\bpan\b|pan de|tortilla de trigo|harina|pasta|espagueti|macarron|arroz|avena|cereal|masa|hojaldre|fideo|cuscus|quinoa|galleta"),
    ("Especias y condimentos", r"\bsal\b|pimienta|pimenton|comino|oregano|canela|curry|nuez moscada|laurel|tomillo|romero|"
                               r"especia|curcuma|cayena|guindilla|vainilla|levadura|bicarbonato"),
    ("Bebidas", r"\bagua\b|vino|cerveza|zumo|refresco|cafe|\bte\b"),
    ("Congelados", r"congelad|helado"),
    ("Despensa", r"aceite|vinagre|azucar|miel|tomate frito|tomate triturado|caldo|lata|garbanzo|lenteja|alubia|soja|"
                 r"mostaza|mayonesa|ketchup|chocolate|cacao|frutos secos|almendra|nuez|pasas|maicena|sesamo|tahini|salsa"),
]


def guess_category_name(name: str) -> str:
    n = U.strip_accents(name.lower())
    for cat, rx in CATEGORY_HINTS:
        if re.search(rx, n):
            return cat
    return "Otros"


class NotFound(Exception):
    pass


class ShoppingService:
    def __init__(self, db: Database, prices=None):
        self.db = db
        self.prices = prices

    # -- categories -------------------------------------------------------
    def categories(self) -> list[dict]:
        return [{"id": r["id"], "nombre": r["name"], "posicion": r["position"]}
                for r in self.db.query("SELECT * FROM shopping_categories ORDER BY position, id")]

    def create_category(self, name: str) -> dict:
        name = name.strip()
        if not name:
            raise ValueError("Nombre vacío")
        if self.db.query("SELECT 1 FROM shopping_categories WHERE name=?", (name,)):
            raise ValueError("Ya existe ese pasillo")
        pos = self.db.query("SELECT COALESCE(MAX(position),-1)+1 p FROM shopping_categories")[0]["p"]
        cid = self.db.execute("INSERT INTO shopping_categories(name,position) VALUES(?,?)", (name, pos)).lastrowid
        return next(c for c in self.categories() if c["id"] == cid)

    def rename_category(self, cid: int, name: str) -> dict:
        if not self.db.execute("UPDATE shopping_categories SET name=? WHERE id=?", (name.strip(), cid)).rowcount:
            raise NotFound
        return next(c for c in self.categories() if c["id"] == cid)

    def delete_category(self, cid: int) -> None:
        if not self.db.execute("DELETE FROM shopping_categories WHERE id=?", (cid,)).rowcount:
            raise NotFound

    def reorder_categories(self, ids: list[int]) -> list[dict]:
        with self.db._lock:
            for i, cid in enumerate(ids):
                self.db.execute("UPDATE shopping_categories SET position=? WHERE id=?", (i, cid))
        return self.categories()

    def _category_id(self, name: str) -> Optional[int]:
        want = guess_category_name(name)
        rows = self.db.query("SELECT id FROM shopping_categories WHERE name=?", (want,))
        if not rows:
            rows = self.db.query("SELECT id FROM shopping_categories WHERE name='Otros'")
        return rows[0]["id"] if rows else None

    # -- pantry -----------------------------------------------------------
    def pantry(self) -> list[dict]:
        return [{"id": r["id"], "nombre": r["name"]} for r in self.db.query("SELECT * FROM pantry ORDER BY name")]

    def add_pantry(self, name: str) -> dict:
        nn = U.norm_name(name)
        if not nn:
            raise ValueError("Nombre vacío")
        self.db.execute("INSERT OR IGNORE INTO pantry(name,name_norm,created) VALUES(?,?,?)", (name.strip(), nn, now()))
        return next(p for p in self.pantry() if U.norm_name(p["nombre"]) == nn)

    def delete_pantry(self, pid: int) -> None:
        if not self.db.execute("DELETE FROM pantry WHERE id=?", (pid,)).rowcount:
            raise NotFound

    def _in_pantry(self, nn: str) -> bool:
        return bool(self.db.query("SELECT 1 FROM pantry WHERE name_norm=?", (nn,)))

    # -- lists ------------------------------------------------------------
    def _list_row(self, lid: int):
        rows = self.db.query("SELECT * FROM shopping_lists WHERE id=?", (lid,))
        if not rows:
            raise NotFound
        return rows[0]

    def lists(self) -> list[dict]:
        out = []
        for r in self.db.query("SELECT * FROM shopping_lists ORDER BY position, id"):
            c = self.db.query("SELECT status, count(*) n FROM shopping_items WHERE list_id=? GROUP BY status", (r["id"],))
            counts = {x["status"]: x["n"] for x in c}
            out.append({"id": r["id"], "nombre": r["name"], "mostrar_precios": bool(r["show_prices"]),
                        "actualizada": r["updated"], "pendientes": counts.get("pendiente", 0),
                        "total": sum(counts.values())})
        return out

    def create_list(self, name: str) -> dict:
        pos = self.db.query("SELECT COALESCE(MAX(position),-1)+1 p FROM shopping_lists")[0]["p"]
        lid = self.db.execute("INSERT INTO shopping_lists(name,created,updated,position) VALUES(?,?,?,?)",
                              (name.strip() or "Lista de la compra", now(), now(), pos)).lastrowid
        return self.get_list(lid)

    def update_list(self, lid: int, nombre: Optional[str] = None, mostrar_precios: Optional[bool] = None,
                    notas: Optional[str] = None) -> dict:
        self._list_row(lid)
        if nombre is not None:
            self.db.execute("UPDATE shopping_lists SET name=? WHERE id=?", (nombre.strip() or "Lista", lid))
        if mostrar_precios is not None:
            self.db.execute("UPDATE shopping_lists SET show_prices=? WHERE id=?", (int(mostrar_precios), lid))
        if notas is not None:
            self.db.execute("UPDATE shopping_lists SET notes=? WHERE id=?", (notas, lid))
        self._touch(lid)
        return self.get_list(lid)

    def delete_list(self, lid: int) -> None:
        if not self.db.execute("DELETE FROM shopping_lists WHERE id=?", (lid,)).rowcount:
            raise NotFound

    def _touch(self, lid: int) -> None:
        self.db.execute("UPDATE shopping_lists SET updated=?, version=version+1 WHERE id=?", (now(), lid))

    def _item_api(self, r) -> dict:
        qty, unit = r["qty"], r["unit"] or "ud"
        shown = U.round_qty(qty, unit, r["name"])[0] if qty is not None else None
        return {"id": r["id"], "lista_id": r["list_id"], "nombre": r["name"], "cantidad": qty, "unidad": unit,
                "texto_cantidad": U.display(shown, unit) if qty is not None else "",
                "estado": r["status"], "nota": r["note"] or "", "categoria_id": r["category_id"],
                "posicion": r["position"], "origenes": json.loads(r["sources"] or "[]"),
                "recurrente": bool(r["recurring"]), "precio_eur": r["price_eur"],
                "precio_fuente": r["price_source"]}

    def get_list(self, lid: int) -> dict:
        r = self._list_row(lid)
        items = [self._item_api(i) for i in self.db.query(
            "SELECT i.* FROM shopping_items i LEFT JOIN shopping_categories c ON c.id=i.category_id "
            "WHERE i.list_id=? ORDER BY COALESCE(c.position, 9999), i.position, i.id", (lid,))]
        show = bool(r["show_prices"])
        priced = [i for i in items if i["estado"] == "pendiente" and i["precio_eur"] is not None]
        total = round(sum(i["precio_eur"] for i in priced), 2) if priced else None
        if not show:
            for i in items:
                i["precio_eur"] = i["precio_fuente"] = None
        return {"id": r["id"], "nombre": r["name"], "mostrar_precios": show, "notas": r["notes"] or "",
                "actualizada": r["updated"], "version": r["version"], "items": items,
                "categorias": self.categories(),
                "precio_estimado_eur": total if show else None, "precio_fuente": "estimado" if show else None,
                "precio_parcial": show and any(i["estado"] == "pendiente" and i["precio_eur"] is None for i in items)}

    # -- items ------------------------------------------------------------
    def _manual_price(self, name: str, qty: Optional[float], unit: str) -> tuple[Optional[float], Optional[str]]:
        if not self.prices or qty is None:
            return None, None
        for e in self.prices.get(name):
            if unit == "g" and e.price_per_kg:
                return round(e.price_per_kg * qty / 1000, 2), e.source
            if unit == "ml" and e.price_per_l:
                return round(e.price_per_l * qty / 1000, 2), e.source
            if unit not in ("g", "ml") and e.price_per_unit:
                return round(e.price_per_unit * qty, 2), e.source
        return None, None

    def add_item(self, lid: int, nombre: str, cantidad: Optional[float] = None, unidad: str = "",
                 nota: str = "", categoria_id: Optional[int] = None, recurrente: bool = False,
                 origen: Optional[dict] = None, precio_eur: Optional[float] = None) -> dict:
        """Add (or merge into) an item. Same normalised name + canonical unit => quantities add up."""
        self._list_row(lid)
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("Nombre vacío")
        nn = U.norm_name(nombre) or nombre.lower()
        manual = origen is None
        if manual:
            origen = {"manual": True, "cantidad": cantidad, "unidad": unidad}
        qty, unit = U.canonical(cantidad, unidad, nombre)
        with self.db._lock:
            existing = self.db.query("SELECT * FROM shopping_items WHERE list_id=? AND name_norm=? AND unit=?",
                                     (lid, nn, unit))
            if existing:
                e = existing[0]
                new_qty = e["qty"] if qty is None else (qty if e["qty"] is None else e["qty"] + qty)
                srcs = json.loads(e["sources"] or "[]") + ([origen] if origen else [])
                price = e["price_eur"]
                if precio_eur is not None:
                    price = round((price or 0) + precio_eur, 2)
                status = "pendiente" if e["status"] == "comprado" else e["status"]
                self.db.execute("UPDATE shopping_items SET qty=?, sources=?, price_eur=?, status=?, updated=?, "
                                "version=version+1 WHERE id=?",
                                (new_qty, json.dumps(srcs, ensure_ascii=False), price, status, now(), e["id"]))
                iid = e["id"]
            else:
                src = "estimado" if precio_eur is not None else None
                if precio_eur is None and manual:
                    precio_eur, src = self._manual_price(nombre, qty, unit)
                cat = categoria_id if categoria_id is not None else self._category_id(nombre)
                pos = self.db.query("SELECT COALESCE(MAX(position),-1)+1 p FROM shopping_items WHERE list_id=?", (lid,))[0]["p"]
                status = "ya_lo_tengo" if self._in_pantry(nn) else "pendiente"
                iid = self.db.execute(
                    "INSERT INTO shopping_items(list_id,category_id,name,name_norm,qty,unit,status,note,position,sources,"
                    "recurring,updated,created,price_eur,price_source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (lid, cat, nombre, nn, qty, unit, status, nota or None, pos,
                     json.dumps([origen] if origen else [], ensure_ascii=False), int(recurrente), now(), now(),
                     precio_eur, src)).lastrowid
            self._touch(lid)
        return self.item(iid)

    def item(self, iid: int) -> dict:
        rows = self.db.query("SELECT * FROM shopping_items WHERE id=?", (iid,))
        if not rows:
            raise NotFound
        return self._item_api(rows[0])

    def update_item(self, iid: int, **changes) -> dict:
        cur = self.item(iid)
        sets, vals = [], []
        if "nombre" in changes and changes["nombre"] is not None:
            sets += ["name=?", "name_norm=?"]
            vals += [changes["nombre"].strip(), U.norm_name(changes["nombre"])]
        if "cantidad" in changes or "unidad" in changes:
            q = changes.get("cantidad", cur["cantidad"])
            u = changes.get("unidad") if changes.get("unidad") is not None else cur["unidad"]
            q, u = U.canonical(q, u, changes.get("nombre") or cur["nombre"])
            sets += ["qty=?", "unit=?"]
            vals += [q, u]
        for key, col, conv in (("estado", "status", str), ("nota", "note", str), ("categoria_id", "category_id", None),
                               ("recurrente", "recurring", int), ("precio_eur", "price_eur", None)):
            if key in changes and (changes[key] is not None or key in ("categoria_id", "precio_eur")):
                v = changes[key]
                if key == "estado" and v not in ESTADOS:
                    raise ValueError("Estado no válido")
                sets.append(f"{col}=?")
                vals.append(conv(v) if conv and v is not None else v)
                if key == "precio_eur":
                    sets.append("price_source=?")
                    vals.append("manual" if v is not None else None)
        if sets:
            self.db.execute(f"UPDATE shopping_items SET {', '.join(sets)}, updated=?, version=version+1 WHERE id=?",
                            (*vals, now(), iid))
            self._touch(cur["lista_id"])
        return self.item(iid)

    def delete_item(self, iid: int) -> None:
        cur = self.item(iid)
        self.db.execute("DELETE FROM shopping_items WHERE id=?", (iid,))
        self._touch(cur["lista_id"])

    def reorder_items(self, lid: int, ids: list[int], categoria_id: Optional[int] = None) -> dict:
        with self.db._lock:
            for i, iid in enumerate(ids):
                if categoria_id is not None:
                    self.db.execute("UPDATE shopping_items SET position=?, category_id=? WHERE id=? AND list_id=?",
                                    (i, categoria_id, iid, lid))
                else:
                    self.db.execute("UPDATE shopping_items SET position=? WHERE id=? AND list_id=?", (i, iid, lid))
        self._touch(lid)
        return self.get_list(lid)

    def clear_done(self, lid: int) -> dict:
        """Remove bought items; recurring ones go back to 'pendiente' instead."""
        with self.db._lock:
            self.db.execute("DELETE FROM shopping_items WHERE list_id=? AND status='comprado' AND recurring=0", (lid,))
            self.db.execute("UPDATE shopping_items SET status='pendiente', sources='[]' WHERE list_id=? AND recurring=1 "
                            "AND status='comprado'", (lid,))
        self._touch(lid)
        return self.get_list(lid)

    # -- from recipes -----------------------------------------------------
    def add_recipe(self, lid: int, recipe: dict, servings: Optional[float] = None, origen_extra: Optional[dict] = None) -> dict:
        base = recipe.get("raciones") or 1
        servings = servings or base
        k = servings / base
        added = 0
        for ing in recipe.get("ingredientes") or []:
            name = (ing.get("nombre") or "").strip()
            if not name:
                continue
            q = ing.get("cantidad_num")
            unit = ing.get("unidad") or ""
            qty = None if q is None else q * k
            price = None if ing.get("precio_eur") is None else round(ing["precio_eur"] * k, 2)
            origen = {"receta_id": recipe.get("id"), "titulo": recipe.get("titulo"), "raciones": servings,
                      "cantidad": qty, "unidad": unit, **(origen_extra or {})}
            self.add_item(lid, name, qty, unit, origen=origen, precio_eur=price)
            added += 1
        lst = self.get_list(lid)
        lst["añadidos"] = added
        return lst

    def remove_recipe(self, lid: int, recipe_id: int) -> dict:
        """Undo a recipe's contributions (items only from that recipe disappear)."""
        with self.db._lock:
            for r in self.db.query("SELECT * FROM shopping_items WHERE list_id=?", (lid,)):
                srcs = json.loads(r["sources"] or "[]")
                mine = [s for s in srcs if s.get("receta_id") == recipe_id]
                if not mine:
                    continue
                rest = [s for s in srcs if s.get("receta_id") != recipe_id]
                if not rest:
                    self.db.execute("DELETE FROM shopping_items WHERE id=?", (r["id"],))
                    continue
                sub = sum((U.canonical(s.get("cantidad"), s.get("unidad") or "", r["name"])[0] or 0) for s in mine)
                qty = None if r["qty"] is None else max(0.0, r["qty"] - sub)
                self.db.execute("UPDATE shopping_items SET qty=?, sources=? WHERE id=?",
                                (qty, json.dumps(rest, ensure_ascii=False), r["id"]))
        self._touch(lid)
        return self.get_list(lid)

    # -- share ------------------------------------------------------------
    def share_text(self, lid: int, incluir_tengo: bool = False) -> dict:
        lst = self.get_list(lid)
        cats = {c["id"]: c["nombre"] for c in lst["categorias"]}
        lines = [f"🛒 {lst['nombre']}"]
        current = object()
        for it in lst["items"]:
            if it["estado"] == "comprado" or (it["estado"] == "ya_lo_tengo" and not incluir_tengo):
                continue
            cat = cats.get(it["categoria_id"], "Otros")
            if cat != current:
                lines += ["", f"*{cat}*"]
                current = cat
            qty = f"{it['texto_cantidad']} " if it["texto_cantidad"] else ""
            note = f" ({it['nota']})" if it["nota"] else ""
            lines.append(f"• {qty}{it['nombre']}{note}")
        if lst["notas"]:
            lines += ["", lst["notas"]]
        if lst["mostrar_precios"] and lst["precio_estimado_eur"] is not None:
            lines += ["", f"Total orientativo (estimado): {lst['precio_estimado_eur']:.2f} €".replace(".", ",")]
        text = "\n".join(lines)
        return {"texto": text, "whatsapp": "https://wa.me/?text=" + quote(text)}
