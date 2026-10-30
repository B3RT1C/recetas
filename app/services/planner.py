"""Weekly meal planner: recipes placed in day/meal slots with their own servings."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from ..db import Database, now

COMIDAS = ("comida", "cena")


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


DEFAULT_SERVINGS = 2
MAX_DEFAULT_SERVINGS = 12


def default_servings(rec: dict) -> float:
    """Servings a new plan entry starts with: the recipe's own declared servings, else 2.

    Estimated servings and batch yields (e.g. "31 tortillas", "for the whole week") are not a
    sensible portion for one meal, so they fall back to the default too.
    """
    n = rec.get("raciones")
    if rec.get("raciones_estimadas") or isinstance(n, bool) or not isinstance(n, (int, float)):
        return DEFAULT_SERVINGS
    return n if 0 < n <= MAX_DEFAULT_SERVINGS else DEFAULT_SERVINGS

class PlannerService:
    def __init__(self, db: Database, recipes):
        self.db = db
        self.recipes = recipes

    def _api(self, r) -> dict:
        rec = self.recipes.get(r["recipe_id"]) or {}
        return {"id": r["id"], "fecha": r["fecha"], "comida": r["comida"], "receta_id": r["recipe_id"],
                "titulo": rec.get("titulo", "(receta borrada)"), "emoji": rec.get("emoji"),
                "portada": rec.get("portada"), "raciones_receta": rec.get("raciones"),
                "raciones": r["raciones"], "nota": r["nota"] or "", "posicion": r["position"]}

    def week(self, start: Optional[str] = None) -> dict:
        d0 = monday(date.fromisoformat(start) if start else date.today())
        days = [(d0 + timedelta(days=i)).isoformat() for i in range(7)]
        rows = self.db.query("SELECT * FROM plan_items WHERE fecha BETWEEN ? AND ? ORDER BY fecha, comida, position, id",
                             (days[0], days[-1]))
        return {"inicio": days[0], "fin": days[-1], "dias": days, "comidas": list(COMIDAS),
                "items": [self._api(r) for r in rows],
                "anterior": (d0 - timedelta(days=7)).isoformat(), "siguiente": (d0 + timedelta(days=7)).isoformat()}

    def get(self, pid: int) -> dict:
        rows = self.db.query("SELECT * FROM plan_items WHERE id=?", (pid,))
        if not rows:
            raise KeyError(pid)
        return self._api(rows[0])

    def add(self, fecha: str, comida: str, receta_id: int, raciones: Optional[float] = None, nota: str = "") -> dict:
        date.fromisoformat(fecha)
        if comida not in COMIDAS:
            raise ValueError("Comida no válida")
        rec = self.recipes.get(receta_id)
        if not rec:
            raise KeyError(receta_id)
        pos = self.db.query("SELECT COALESCE(MAX(position),-1)+1 p FROM plan_items WHERE fecha=? AND comida=?",
                            (fecha, comida))[0]["p"]
        pid = self.db.execute("INSERT INTO plan_items(fecha,comida,recipe_id,raciones,nota,position,created) "
                              "VALUES(?,?,?,?,?,?,?)",
                              (fecha, comida, receta_id, raciones or default_servings(rec), nota or None, pos, now())).lastrowid
        return self.get(pid)

    def update(self, pid: int, fecha: Optional[str] = None, comida: Optional[str] = None,
               raciones: Optional[float] = None, nota: Optional[str] = None, posicion: Optional[int] = None) -> dict:
        cur = self.get(pid)
        if fecha is not None:
            date.fromisoformat(fecha)
        if comida is not None and comida not in COMIDAS:
            raise ValueError("Comida no válida")
        f, c = fecha or cur["fecha"], comida or cur["comida"]
        moved = (f, c) != (cur["fecha"], cur["comida"])
        pos = posicion
        if pos is None and moved:
            pos = self.db.query("SELECT COALESCE(MAX(position),-1)+1 p FROM plan_items WHERE fecha=? AND comida=?",
                                (f, c))[0]["p"]
        with self.db._lock:
            if posicion is not None:  # shift the others in the target slot
                self.db.execute("UPDATE plan_items SET position=position+1 WHERE fecha=? AND comida=? AND position>=? AND id<>?",
                                (f, c, posicion, pid))
            self.db.execute("UPDATE plan_items SET fecha=?, comida=?, raciones=?, nota=?, position=? WHERE id=?",
                            (f, c, raciones if raciones is not None else cur["raciones"],
                             nota if nota is not None else (cur["nota"] or None),
                             pos if pos is not None else cur["posicion"], pid))
        return self.get(pid)

    def delete(self, pid: int) -> None:
        if not self.db.execute("DELETE FROM plan_items WHERE id=?", (pid,)).rowcount:
            raise KeyError(pid)

    def to_list(self, shopping, list_id: int, inicio: str, fin: str, ids: Optional[list[int]] = None) -> dict:
        rows = self.db.query("SELECT * FROM plan_items WHERE fecha BETWEEN ? AND ? ORDER BY fecha", (inicio, fin))
        n = 0
        for r in rows:
            if ids and r["id"] not in ids:
                continue
            rec = self.recipes.get(r["recipe_id"])
            if rec and rec.get("ingredientes"):
                shopping.add_recipe(list_id, rec, r["raciones"], {"plan": f"{r['fecha']} {r['comida']}"})
                n += 1
        lst = shopping.get_list(list_id)
        lst["recetas_añadidas"] = n
        return lst
