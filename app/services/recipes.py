"""Recipe repository: CRUD + search on top of the SQLite document store."""
from __future__ import annotations
from .source_link import with_source

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

from ..config import Settings
from ..db import ESTADO_COMPLETA, ESTADO_PENDIENTE, Database, now, shortcode_of
from .tags import norm, suggest_allergens, suggest_tags

UNIT_LABELS = {"ud": "", "diente": "diente(s)", "taza": "taza(s)"}


class DuplicateError(Exception):
    pass


def _fmt_qty(q: Optional[float], unit: str) -> str:
    if q is None:
        return ""
    if unit in ("g", "ml") and q >= 1000:
        return f"{q / 1000:g}".replace(".", ",") + (" kg" if unit == "g" else " l")
    label = UNIT_LABELS.get(unit, unit)
    return (f"{round(q, 2):g}".replace(".", ",") + " " + label).strip()


def fuzzy_contains(term: str, words: list[str], haystack: str) -> bool:
    """Accent-insensitive substring match, tolerant to small typos (e.g. 'polo' -> 'pollo')."""
    if term in haystack:
        return True
    if len(term) < 4:
        return False
    limit = 0.85 if len(term) < 7 else 0.8
    return any(w[:1] == term[:1] and abs(len(w) - len(term)) <= 2 and SequenceMatcher(None, term, w).ratio() >= limit
               for w in words)


def normalize(data: dict) -> dict:
    """Fill derived fields of a manually created / imported recipe (never overwrite given values)."""
    for computed in ("portada", "media", "estado", "id", "shortcode"):
        data.pop(computed, None)
    if data.get("tipo", "receta") != "receta":
        return data
    raciones = data.get("raciones") or 2
    data["raciones"] = raciones
    for ing in data.get("ingredientes", []):
        q = ing.get("cantidad_num")
        if not ing.get("cantidad_normal"):
            ing["cantidad_normal"] = _fmt_qty(q, ing.get("unidad", "ud"))
        if not ing.get("cantidad_1"):
            ing["cantidad_1"] = _fmt_qty(q / raciones if q is not None else None, ing.get("unidad", "ud"))
    prices = [i.get("precio_eur") for i in data.get("ingredientes", []) if i.get("precio_eur") is not None]
    if data.get("precio_total_eur") is None and prices:
        data["precio_total_eur"] = round(sum(prices), 2)
    if data.get("precio_racion_eur") is None and data.get("precio_total_eur") is not None:
        data["precio_racion_eur"] = round(data["precio_total_eur"] / raciones, 2)
    if data.get("tiempo_total_min") is None:
        mins = [p.get("minutos") or 0 for p in data.get("pasos", [])]
        data["tiempo_total_min"] = sum(mins) if mins else None
    return data


class RecipeService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    # -- media -------------------------------------------------------------
    def media_for(self, shortcode: Optional[str], data: dict) -> dict:
        """Resolve local media URLs; anything missing on disk is reported as null."""
        out: dict[str, Optional[str]] = {"video": None, "foto": None}
        for kind in ("video", "foto"):
            rel = data.get(kind)
            if rel:
                if self._path_for_url(rel).exists():
                    out[kind] = "/" + rel.lstrip("/")
        if not out["video"] and shortcode and (self.settings.videos_dir / f"{shortcode}.mp4").exists():
            out["video"] = f"/videos/{shortcode}.mp4"
        if not out["foto"] and shortcode:
            for ext in ("jpg", "webp", "png"):
                if (self.settings.media_dir / "photos" / f"{shortcode}.{ext}").exists():
                    out["foto"] = f"/media/photos/{shortcode}.{ext}"
                    break
        return out

    def _path_for_url(self, rel: str) -> Path:
        rel = rel.lstrip("/")
        if rel.startswith("videos/"):
            return self.settings.videos_dir / rel[len("videos/"):]
        if rel.startswith("media/"):
            return self.settings.media_dir / rel[len("media/"):]
        return self.settings.media_dir / "__invalid__"

    def local_files(self, recipe: dict) -> list[tuple[Path, str]]:
        """(absolute path, archive name) of the media that exists for a recipe."""
        files = []
        for url in (recipe.get("media") or {}).values():
            if url:
                p = self._path_for_url(url)
                if p.exists():
                    files.append((p, url.lstrip("/")))
        return files

    # -- read --------------------------------------------------------------
    def _row_to_api(self, row) -> dict:
        data = json.loads(row["data"])
        out = {"id": row["id"], "tipo": row["tipo"], "shortcode": row["shortcode"],
               "estado": ESTADO_COMPLETA if row["tipo"] == "receta" else ESTADO_PENDIENTE, **data}
        with_source(out, row["shortcode"])
        out["media"] = self.media_for(row["shortcode"], data)
        thumbs = getattr(self, "thumbs", None)
        if thumbs is not None:
            video = out["media"]["video"]
            out["portada"] = thumbs.cover(row["shortcode"] or f"r{row['id']}",
                                          self._path_for_url(video) if video else None, out["media"]["foto"])
        else:
            out["portada"] = out["media"]["foto"]
        return out

    def get(self, rid: int) -> Optional[dict]:
        rows = self.db.query("SELECT * FROM recipes WHERE id=?", (rid,))
        return self._row_to_api(rows[0]) if rows else None

    def get_by_shortcode(self, shortcode: str) -> Optional[dict]:
        rows = self.db.query("SELECT * FROM recipes WHERE shortcode=?", (shortcode,))
        return self._row_to_api(rows[0]) if rows else None

    def existing_shortcodes(self) -> set[str]:
        return {r["shortcode"] for r in self.db.query("SELECT shortcode FROM recipes WHERE shortcode IS NOT NULL")}

    def all(self) -> list[dict]:
        rows = self.db.query("SELECT * FROM recipes ORDER BY tipo, COALESCE(legacy_order, 1000000), id")
        return [self._row_to_api(r) for r in rows]

    def search(
        self,
        q: str = "",
        tipo: Optional[str] = None,
        etiqueta: Optional[str] = None,
        max_min: Optional[int] = None,
        max_precio: Optional[float] = None,
        orden: str = "original",
        estado: Optional[str] = None,
        favoritos: bool = False,
    ) -> list[dict]:
        terms = [t for t in norm(q).split() if t]
        out = []
        for r in self.all():
            if tipo and r["tipo"] != tipo:
                continue
            if estado and r["estado"] != estado:
                continue
            if favoritos and not r.get("favorito"):
                continue
            if etiqueta and etiqueta not in r.get("etiquetas", []):
                continue
            if max_min is not None and (r.get("tiempo_total_min") is None or r["tiempo_total_min"] > max_min):
                continue
            if max_precio is not None and (r.get("precio_racion_eur") is None or r["precio_racion_eur"] > max_precio):
                continue
            if terms:
                hay = norm(" ".join([
                    r.get("titulo", ""), r.get("autor", ""), r.get("nota") or "", " ".join(r.get("etiquetas", [])),
                    " ".join(i.get("nombre", "") for i in r.get("ingredientes", [])),
                ]))
                words = re.findall(r"\w+", hay)
                if not all(fuzzy_contains(t, words, hay) for t in terms):
                    continue
            out.append(r)
        keys = {
            "rapidas": lambda r: (r.get("tiempo_total_min") is None, r.get("tiempo_total_min") or 0),
            "baratas": lambda r: (r.get("precio_racion_eur") is None, r.get("precio_racion_eur") or 0),
            "az": lambda r: norm(r.get("titulo", "")),
            "recientes": lambda r: -r["id"],
            "valoracion": lambda r: -(r.get("valoracion") or 0),
        }
        if orden in keys:
            out.sort(key=keys[orden])
        return out

    def tags(self) -> list[dict]:
        counts: dict[str, int] = {}
        for r in self.all():
            for t in r.get("etiquetas", []):
                counts[t] = counts.get(t, 0) + 1
        return [{"etiqueta": k, "total": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    # -- write -------------------------------------------------------------
    def create(self, payload: dict, origen: str = "manual") -> dict:
        data = normalize({k: v for k, v in payload.items() if k not in ("id", "media", "shortcode", "estado")})
        if not data.get("etiquetas"):
            data["etiquetas"] = suggest_tags(data)
        if not data.get("alergenos"):
            data["alergenos"] = suggest_allergens(data)
        tipo = data.pop("tipo", "receta")
        sc = payload.get("shortcode") or shortcode_of(data.get("video_url"))
        if sc and self.get_by_shortcode(sc):
            raise DuplicateError(sc)
        data.setdefault("origen", origen)
        data["creado"] = now()
        cur = self.db.execute(
            "INSERT INTO recipes(tipo,shortcode,data) VALUES(?,?,?)", (tipo, sc, json.dumps(data, ensure_ascii=False))
        )
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update(self, rid: int, payload: dict) -> Optional[dict]:
        rows = self.db.query("SELECT * FROM recipes WHERE id=?", (rid,))
        if not rows:
            return None
        old = json.loads(rows[0]["data"])
        data = {k: v for k, v in payload.items() if k not in ("id", "media", "shortcode", "estado")}
        tipo = data.pop("tipo", rows[0]["tipo"])
        for k in ("origen", "creado", "foto", "video"):  # server-managed
            if k in old:
                data[k] = old[k]
        data = normalize({**data, "tipo": tipo})
        data.pop("tipo", None)
        data["actualizado"] = now()
        sc = rows[0]["shortcode"] or shortcode_of(data.get("video_url"))
        if sc and sc != rows[0]["shortcode"]:
            other = self.get_by_shortcode(sc)
            if other and other["id"] != rid:
                raise DuplicateError(sc)
        self.db.execute("UPDATE recipes SET tipo=?, shortcode=?, data=? WHERE id=?",
                        (tipo, sc, json.dumps(data, ensure_ascii=False), rid))
        return self.get(rid)

    def _patch_data(self, rid: int, fn) -> Optional[dict]:
        rows = self.db.query("SELECT data FROM recipes WHERE id=?", (rid,))
        if not rows:
            return None
        data = json.loads(rows[0]["data"])
        fn(data)
        self.db.execute("UPDATE recipes SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), rid))
        return self.get(rid)

    def patch(self, rid: int, changes: dict) -> Optional[dict]:
        return self._patch_data(rid, lambda d: d.update({k: v for k, v in changes.items() if v is not None}))

    def add_cook_log(self, rid: int, entry: dict) -> Optional[dict]:
        return self._patch_data(rid, lambda d: d.setdefault("cocinado", []).append(entry))

    def delete_cook_log(self, rid: int, index: int) -> Optional[dict]:
        def fn(d):
            log = d.get("cocinado", [])
            if 0 <= index < len(log):
                log.pop(index)
        return self._patch_data(rid, fn)

    def set_media_field(self, rid: int, kind: str, rel_url: Optional[str]) -> None:
        rows = self.db.query("SELECT data FROM recipes WHERE id=?", (rid,))
        data = json.loads(rows[0]["data"])
        if rel_url:
            data[kind] = rel_url
        else:
            data.pop(kind, None)
        self.db.execute("UPDATE recipes SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), rid))

    def delete(self, rid: int) -> bool:
        return self.db.execute("DELETE FROM recipes WHERE id=?", (rid,)).rowcount > 0

    # -- legacy ------------------------------------------------------------
    def legacy_document(self, ids: Optional[set[int]] = None) -> dict:
        """Rebuild the v1 recetas.json shape (used by the legacy export and the migration test)."""
        from ..db import V2_KEYS
        meta = json.loads(self.db.get_meta("legacy_meta") or "{}")
        doc: dict[str, Any] = {**meta, "recetas": [], "solo_video": []}
        for r in self.all():
            if ids is not None and r["id"] not in ids:
                continue
            item = {k: v for k, v in r.items() if k not in V2_KEYS and k not in ("id", "tipo", "shortcode", "media", "estado", "portada", "source_url", "source_type")}
            if r["tipo"] == "receta":
                doc["recetas"].append({"id": r["id"], **item})
            else:
                doc["solo_video"].append(item)
        return doc
