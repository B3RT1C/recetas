"""Cover picker API (v2.1.2): choose original / frame / upload / generic, preview frames, global default.

Everything under /api/, so the session middleware enforces login and CSRF on writes.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .services import covers, imgmeta
from .services.thumbs import BLACK_LUMA

PHOTO_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


class CoverIn(BaseModel):
    fuente: Optional[Literal["original", "frame", "upload", "generic"]] = None  # null = default global
    segundo: Optional[float] = Field(default=None, ge=0, le=36000)
    biblioteca: Optional[str] = Field(default=None, pattern=r"^[\w-]{1,80}$")


class CoverDefaultIn(BaseModel):
    predeterminada: Literal["original", "frame", "generic"]


def _sniff(head: bytes) -> Optional[str]:
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def register(app: FastAPI, svc, get_or_404) -> None:
    st = svc.settings
    rs = svc.recipes

    @app.get("/api/portadas/biblioteca", tags=["portadas"])
    def cover_library():
        """Fotos genéricas libres (CC0 / dominio público) con su crédito."""
        return covers.library()

    @app.get("/api/ajustes/portada", tags=["ajustes"])
    def get_cover_default():
        return {"predeterminada": rs.cover_default(), "opciones": list(covers.DEFAULTS),
                "ffmpeg": bool(svc.thumbs and svc.thumbs.available())}

    @app.put("/api/ajustes/portada", tags=["ajustes"])
    def put_cover_default(body: CoverDefaultIn):
        svc.db.set_setting(covers.SETTING, body.predeterminada)
        return {"predeterminada": body.predeterminada}

    @app.put("/api/recipes/{rid}/portada", tags=["portadas"])
    def set_cover(rid: int, body: CoverIn):
        """Elige la portada. Una portada subida, de fotograma o genérica nunca se pisa al reimportar."""
        get_or_404(rid)
        try:
            return covers.choose(rs, rid, body.fuente, body.segundo, body.biblioteca)
        except covers.CoverError as e:
            raise HTTPException(422, str(e)) from None

    @app.get("/api/recipes/{rid}/portada/fotograma", tags=["portadas"])
    def frame_preview(rid: int, t: float = Query(ge=0, le=36000), ancho: int = Query(default=480, ge=120, le=960)):
        """Vista previa (JPEG) del fotograma en el segundo ``t``, extraída en el servidor con ffmpeg."""
        r = get_or_404(rid)
        video = r["media"].get("video")
        if not video:
            raise HTTPException(404, "La receta no tiene vídeo local")
        if not (svc.thumbs and svc.thumbs.available()):
            raise HTTPException(503, "ffmpeg no está disponible")
        path = rs._path_for_url(video)
        fd, tmp = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            if not svc.thumbs.render_frame(path, t, Path(tmp), width=ancho):
                raise HTTPException(422, "No hay fotograma en ese segundo")
            data = Path(tmp).read_bytes()
            y = svc.thumbs.luma(Path(tmp))
        finally:
            os.unlink(tmp)
        headers = {"Cache-Control": "private, max-age=3600"}
        if y is not None:  # lets the picker warn about a black frame
            headers["X-Luma"] = f"{y:.0f}"
            headers["X-Fotograma-Negro"] = "1" if y < BLACK_LUMA else "0"
        return Response(data, media_type="image/jpeg", headers=headers)

    @app.post("/api/recipes/{rid}/portada/subir", tags=["portadas"])
    async def upload_cover(rid: int, file: UploadFile = File(...)):
        """Sube una foto de portada (JPEG/PNG/WebP, máx. RECETAS_MAX_PHOTO_MB). Se eliminan EXIF/XMP/GPS."""
        get_or_404(rid)
        limit = st.max_photo_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"Archivo demasiado grande (máx. {st.max_photo_mb} MB)")
        ext = _sniff(data[:16])
        if ext not in PHOTO_TYPES:
            raise HTTPException(415, "Formato no admitido. Usa: jpg, png, webp")
        try:
            clean = imgmeta.strip(data, ext)
        except imgmeta.BadImage as e:
            raise HTTPException(415, f"Imagen no válida: {e}") from None
        orient = imgmeta.jpeg_orientation(data) if ext == "jpg" else 1
        dest_dir = st.media_dir / "recipes" / str(rid)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for old in dest_dir.glob("portada.*"):
            old.unlink()
        final = dest_dir / f"portada.{ext}"
        tmp = dest_dir / f".portada.part.{ext}"
        tmp.write_bytes(clean)
        vf = imgmeta.orientation_filter(orient)
        exe = svc.thumbs.ffmpeg_path() if svc.thumbs else None
        if vf and exe:  # bake EXIF rotation into the pixels, since the tag is gone
            rot = dest_dir / ".portada.rot.jpg"
            r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-i", str(tmp), "-vf", vf,
                                "-map_metadata", "-1", "-q:v", "3", str(rot)], capture_output=True, timeout=60)
            if r.returncode == 0 and rot.exists():
                os.replace(rot, tmp)
            rot.unlink(missing_ok=True)
        os.replace(tmp, final)
        return rs.set_cover(rid, "upload", f"media/recipes/{rid}/{final.name}")
