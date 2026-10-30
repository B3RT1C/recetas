"""Per-user UI preferences (currently: recipe list view mode and grid density).

Lives under /api/ so the session middleware enforces login and CSRF on PUT.
"""
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

VIEWS = ("una", "info", "detalle", "cuadricula")
DEFAULT = {"vista": "cuadricula", "densidad": 4}


class ListPrefsIn(BaseModel):
    vista: Literal["una", "info", "detalle", "cuadricula"]
    densidad: int = Field(default=4, ge=2, le=8)


def _key(request: Request) -> str:
    return f"prefs:{request.state.user['usuario'].lower()}:lista"


def register(app: FastAPI, svc) -> None:
    db = svc.db

    @app.get("/api/preferencias/lista", tags=["ajustes"])
    def get_list_prefs(request: Request):
        saved = db.get_setting(_key(request)) or {}
        out = dict(DEFAULT)
        if saved.get("vista") in VIEWS:
            out["vista"] = saved["vista"]
        if isinstance(saved.get("densidad"), int) and 2 <= saved["densidad"] <= 8:
            out["densidad"] = saved["densidad"]
        return out

    @app.put("/api/preferencias/lista", tags=["ajustes"])
    def put_list_prefs(body: ListPrefsIn, request: Request):
        val = {"vista": body.vista, "densidad": body.densidad}
        db.set_setting(_key(request), val)
        return val
