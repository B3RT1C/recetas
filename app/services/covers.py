"""Cover choice (v2.1.2): original thumbnail, video frame, uploaded photo or a generic CC0 photo.

Per recipe: columns ``cover_source`` / ``cover_param`` (NULL = follow the global default stored in
settings under ``portada:predeterminada``). Resolution lives in ``RecipeService._cover``.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

from ..config import ROOT

SOURCES = ("original", "frame", "upload", "generic")
DEFAULTS = ("original", "frame", "generic")  # global default choices (upload is per recipe only)
SETTING = "portada:predeterminada"
LIBRARY_DIR = ROOT / "data" / "sample" / "covers"
_ROW = re.compile(r"^\|\s*([\w-]+)\.jpg\s*\|\s*\[([^\]]+)\]\((\S+)\)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")


def _title(lid: str) -> str:
    return lid.replace("-", " ").capitalize()


def library(directory: Path = LIBRARY_DIR) -> list[dict]:
    """Generic photos with their credits (parsed from ATTRIBUTION.md)."""
    credits: dict[str, dict] = {}
    att = directory / "ATTRIBUTION.md"
    if att.exists():
        for line in att.read_text(encoding="utf-8").splitlines():
            m = _ROW.match(line)
            if m:
                credits[m[1]] = {"fuente": m[2], "url": m[3], "autor": m[4], "licencia": m[5]}
    out = []
    for p in sorted(directory.glob("*.jpg")) if directory.exists() else []:
        c = credits.get(p.stem, {})
        out.append({"id": p.stem, "titulo": _title(p.stem), "url": f"/media/library/{p.name}",
                    "autor": c.get("autor"), "licencia": c.get("licencia"), "fuente_url": c.get("url"),
                    "credito": f"{c['autor']} · {c['licencia']} · Wikimedia Commons" if c else None})
    return out


def library_ids(directory: Path = LIBRARY_DIR) -> list[str]:
    return [p.stem for p in sorted(directory.glob("*.jpg"))] if directory.exists() else []


def ensure_library_file(media_dir: Path, lid: str, directory: Path = LIBRARY_DIR) -> Optional[str]:
    """Copy a library photo into <media>/library/ (served statically, exported with the recipe)."""
    if not re.fullmatch(r"[\w-]+", lid or ""):
        return None
    src = directory / f"{lid}.jpg"
    if not src.exists():
        return None
    dst = media_dir / "library" / src.name
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return f"/media/library/{src.name}"


def generic_for(rid: int, directory: Path = LIBRARY_DIR) -> Optional[str]:
    """Deterministic library pick when the global default is 'generic' and the recipe chose nothing."""
    ids = library_ids(directory)
    return ids[rid % len(ids)] if ids else None


class CoverError(ValueError):
    pass


def choose(recipes, rid: int, fuente: Optional[str], segundo: Optional[float] = None,
           biblioteca: Optional[str] = None) -> dict:
    """Validate and store a cover choice (shared by the web API and MCP). ``fuente=None`` = global default."""
    r = recipes.get(rid)
    if not r:
        raise LookupError("Receta no encontrada")
    param: Optional[str] = None
    if fuente == "frame":
        if not r["media"].get("video"):
            raise CoverError("La receta no tiene vídeo local")
        if segundo is None or not (0 <= segundo <= 36000):
            raise CoverError("Indica el segundo del fotograma")
        thumbs = getattr(recipes, "thumbs", None)
        if thumbs is None or not thumbs.available():
            raise CoverError("ffmpeg no está disponible")
        param = f"{round(segundo, 2):g}"
    elif fuente == "generic":
        if biblioteca not in library_ids():
            raise CoverError("Foto genérica desconocida")
        param = biblioteca
    elif fuente == "upload":
        prev = r.get("portada_param") if r.get("portada_fuente") == "upload" else None
        param = prev or _existing_upload(recipes, rid)
        if not param:
            raise CoverError("Primero sube una foto")
    elif fuente not in (None, "original"):
        raise CoverError("Origen de portada no válido")
    out = recipes.set_cover(rid, fuente, param)
    if fuente == "frame" and out.get("portada_efectiva") != "frame":
        raise CoverError("No se pudo extraer ese fotograma")
    return out


def _existing_upload(recipes, rid: int) -> Optional[str]:
    d = recipes.settings.media_dir / "recipes" / str(rid)
    for p in sorted(d.glob("portada.*")) if d.exists() else []:
        return f"media/recipes/{rid}/{p.name}"
    return None
