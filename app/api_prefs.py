"""UI preferences for the recipe list: view mode + grid density (per user) and list thumbnails (global).

Lives under /api/ so the session middleware enforces login and CSRF on PUT.

v2.1.3 view values: una | compacta | miniatura | cuadricula. Old values are still accepted on PUT and
migrated on read: 'info' (rows with a thumbnail) -> 'miniatura', 'detalle' (big-photo cards) -> 'miniatura'.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

VIEWS = ("una", "compacta", "miniatura", "cuadricula")
LEGACY_VIEWS = {"info": "miniatura", "detalle": "miniatura"}
THUMBS = ("portada", "icono")
THUMBS_KEY = "lista:miniaturas"
DEFAULT = {"vista": "cuadricula", "densidad": 4, "miniaturas": "portada"}


def normalize_view(v) -> Optional[str]:
    v = LEGACY_VIEWS.get(v, v)
    return v if v in VIEWS else None


def get_thumbs(db) -> str:
    v = db.get_setting(THUMBS_KEY)
    return v if v in THUMBS else DEFAULT["miniaturas"]


def set_thumbs(db, value: str) -> str:
    if value not in THUMBS:
        raise ValueError("miniaturas debe ser 'portada' o 'icono'")
    db.set_setting(THUMBS_KEY, value)
    return value


class ListPrefsIn(BaseModel):
    vista: Optional[Literal["una", "compacta", "miniatura", "cuadricula", "info", "detalle"]] = None
    densidad: Optional[int] = Field(default=None, ge=2, le=8)
    miniaturas: Optional[Literal["portada", "icono"]] = None  # icono genérico o miniatura del vídeo/portada


def _key(request: Request) -> str:
    return f"prefs:{request.state.user['usuario'].lower()}:lista"


def register(app: FastAPI, svc) -> None:
    db = svc.db

    def read(request: Request) -> dict:
        saved = db.get_setting(_key(request)) or {}
        out = dict(DEFAULT)
        v = normalize_view(saved.get("vista"))
        if v:
            out["vista"] = v
        if isinstance(saved.get("densidad"), int) and 2 <= saved["densidad"] <= 8:
            out["densidad"] = saved["densidad"]
        out["miniaturas"] = get_thumbs(db)
        return out

    @app.get("/api/preferencias/lista", tags=["ajustes"])
    def get_list_prefs(request: Request):
        """Vista por defecto del servidor (cada dispositivo puede recordar la suya en localStorage)."""
        return read(request)

    @app.put("/api/preferencias/lista", tags=["ajustes"])
    def put_list_prefs(body: ListPrefsIn, request: Request):
        if body.vista is None and body.densidad is None and body.miniaturas is None:
            raise HTTPException(422, "Nada que guardar")
        cur = read(request)
        user = {"vista": normalize_view(body.vista) if body.vista else cur["vista"],
                "densidad": body.densidad if body.densidad is not None else cur["densidad"]}
        db.set_setting(_key(request), user)
        if body.miniaturas:
            set_thumbs(db, body.miniaturas)
        return read(request)
