"""Import validation: never create an empty or broken recipe.

Every check returns the same structured result, shared by the web UI, the
REST API (/api/v1) and the MCP ``import_recipe`` tool::

    {"ok": bool, "code": str|None, "reason_es": str, "reason_en": str,
     "details": dict, "salvageable": bool}

``salvageable`` means the post had *something* useful (a title, some
ingredients or steps, a video) so the UI can offer "Guardar como borrador"
or "Completar a mano" instead of discarding it.
"""
from __future__ import annotations

import re
from typing import Optional

from ..db import shortcode_of

CODES = {
    # code: (reason_es, reason_en, http_status)
    "NOT_FOUND": ("La publicación no existe o ha sido eliminada.", "The post does not exist or was deleted.", 404),
    "PRIVATE": ("La publicación es privada o no tienes acceso.", "The post is private or not accessible.", 403),
    "UNSUPPORTED_SOURCE": ("Fuente no compatible: por ahora solo se admiten publicaciones de Instagram.",
                           "Unsupported source: only Instagram posts are supported for now.", 422),
    "NO_INGREDIENTS": ("No parece una receta: no hay ingredientes.", "This does not look like a recipe: no ingredients found.", 422),
    "NO_STEPS": ("No parece una receta completa: no hay pasos de preparación.", "Incomplete recipe: no preparation steps found.", 422),
    "INSUFFICIENT_DATA": ("No hay datos suficientes para crear una receta.", "Not enough data to create a recipe.", 422),
    "RATE_LIMITED": ("Instagram está limitando las peticiones. Espera unos minutos y vuelve a intentarlo.",
                     "Instagram is rate limiting requests. Wait a few minutes and try again.", 429),
    "NETWORK": ("No se pudo conectar con la fuente. Revisa la conexión y reintenta.",
                "Could not reach the source. Check the connection and retry.", 502),
}

SUPPORTED_HOSTS = re.compile(r"^https?://(www\.|m\.)?instagram\.com/", re.I)


def result(code: Optional[str] = None, details: Optional[dict] = None, salvageable: bool = False,
           reason_es: str = "") -> dict:
    if code is None:
        return {"ok": True, "code": None, "reason_es": "", "reason_en": "", "details": details or {}, "salvageable": False}
    es, en, _ = CODES[code]
    return {"ok": False, "code": code, "reason_es": reason_es or es, "reason_en": en,
            "details": details or {}, "salvageable": salvageable}


def http_status(code: str) -> int:
    return CODES.get(code, ("", "", 422))[2]


class ImportValidationError(Exception):
    """Raised by the importer; carries the structured validation result."""

    def __init__(self, res: dict):
        super().__init__(res["reason_es"])
        self.result = res

    @property
    def code(self) -> str:
        return self.result["code"]


def check_source(url: str) -> dict:
    url = (url or "").strip()
    if not SUPPORTED_HOSTS.match(url) or not shortcode_of(url):
        return result("UNSUPPORTED_SOURCE", {"url": url[:300]})
    return result()


def _has_text(x) -> bool:
    return bool(x and str(x).strip())


def check_recipe(draft: dict, *, has_media: bool = False) -> dict:
    """Validate an extracted (or user-submitted) recipe before it is saved."""
    ings = [i for i in (draft.get("ingredientes") or []) if _has_text(i.get("nombre") if isinstance(i, dict) else i)]
    steps = [p for p in (draft.get("pasos") or []) if _has_text(p.get("texto") if isinstance(p, dict) else p)]
    title = _has_text(draft.get("titulo"))
    details = {"ingredientes": len(ings), "pasos": len(steps), "titulo": title}
    if ings and steps:
        return result(details=details)
    salv = bool(ings or steps or has_media or (title and _has_text(draft.get("caption_original"))))
    if not ings and not steps:
        return result("INSUFFICIENT_DATA" if not salv or not title else "NO_INGREDIENTS", details, salvageable=salv)
    if not ings:
        return result("NO_INGREDIENTS", details, salvageable=True)
    return result("NO_STEPS", details, salvageable=True)


def classify_error(e: Exception) -> dict:
    """Map a provider error to a structured result (uses ``e.code`` when the provider set one)."""
    code = getattr(e, "code", None)
    if code not in CODES:
        msg = str(e).lower()
        if "429" in msg or "limitando" in msg or "rate" in msg:
            code = "RATE_LIMITED"
        elif "no encontrada" in msg or "not found" in msg or "no existe" in msg:
            code = "NOT_FOUND"
        elif "privad" in msg or "private" in msg:
            code = "PRIVATE"
        else:
            code = "NETWORK"
    return result(code, {"mensaje": str(e)[:300]})
