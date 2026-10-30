"""FastAPI application: JSON API + static frontend + media + MCP."""
from __future__ import annotations

import contextlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr

from . import __version__
from .config import ROOT, Settings
from .db import Database
from .mcp_server import BearerAuthASGI, build_mcp
from .models import AIConfigIn, CookLog, ExportRequest, RecipeIn, RecipePatch, TokenCreate
from .services.ai import AIError, AIService
from .services.caption_parser import parse_caption
from .services.exporter import build_export
from .services.importer import ImportService
from .services.instagram import InstagramError, InstagramProvider, is_cdn_url, make_provider
from .services.recipes import DuplicateError, RecipeService
from .services.secrets import SecretBox
from .services.tokens import TokenService

log = logging.getLogger("recetas")
STATIC = ROOT / "static"


@dataclass
class Services:
    settings: Settings
    db: Database
    recipes: RecipeService
    ai: AIService
    instagram: InstagramProvider
    importer: ImportService
    tokens: TokenService
    prices: Optional["PriceCache"] = None


def build_services(settings: Optional[Settings] = None, ig_provider: Optional[InstagramProvider] = None,
                   import_delay: float = 2.0) -> Services:
    settings = settings or Settings()
    settings.ensure_dirs()
    db = Database(settings.db_path)
    db.seed_from_legacy(settings.seed_file)
    recipes = RecipeService(db, settings)
    ai = AIService(db, SecretBox(settings.secret_dir))
    ig = ig_provider or make_provider(settings.ig_provider, settings.secret_dir)
    importer = ImportService(db, settings, recipes, ai, ig, delay_s=0 if settings.ig_provider == "mock" else import_delay)
    from .services.prices import PriceCache
    return Services(settings, db, recipes, ai, ig, importer, TokenService(db), PriceCache(db))


# ---------------------------------------------------------------- request models
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: SecretStr = Field(min_length=1, max_length=200)


class CodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=10)


class CookiesIn(BaseModel):
    sessionid: SecretStr = SecretStr("")
    cookies: SecretStr = SecretStr("")


class ImportItem(BaseModel):
    shortcode: str = Field(pattern=r"^[A-Za-z0-9_-]{5,40}$")
    contenido: Literal["video", "foto", "ambos"] = "ambos"


class ImportIn(BaseModel):
    items: list[ImportItem] = Field(min_length=1, max_length=500)


class CaptionIn(BaseModel):
    caption: str = Field(max_length=20000)
    autor: str = ""
    video_url: str = ""


class AITransformIn(BaseModel):
    recipe_id: Optional[int] = None
    recipe: Optional[dict] = None
    lang: str = Field(default="en", max_length=20)


class ImportUrlIn(BaseModel):
    url: str = Field(max_length=500)


PHOTO_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
VIDEO_TYPES = {"mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime"}


def sniff(head: bytes) -> Optional[str]:
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[4:8] == b"ftyp":
        return "mov" if head[8:10] == b"qt" else "mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    return None


def create_app(services: Optional[Services] = None) -> FastAPI:
    svc = services or build_services()
    st = svc.settings
    mcp = build_mcp(svc)
    mcp_app = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True, json_response=True, host=st.host)

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title="Recetario C API", version=__version__, lifespan=lifespan,
        description="API del recetario. Las rutas `/api/v1/*` son para agentes externos y requieren "
                    "`Authorization: Bearer rct_...` (crea el token en Ajustes → Acceso para agentes). "
                    "Servidor MCP en `/mcp`.",
    )
    app.state.services = svc

    # ------------------------------------------------------------ errors
    @app.exception_handler(InstagramError)
    async def _ig_err(_r: Request, e: InstagramError):
        return JSONResponse({"detail": str(e)}, status_code=400)

    @app.exception_handler(AIError)
    async def _ai_err(_r: Request, e: AIError):
        return JSONResponse({"detail": str(e)}, status_code=502)

    @app.exception_handler(DuplicateError)
    async def _dup(_r: Request, e: DuplicateError):
        existing = svc.recipes.get_by_shortcode(str(e))
        return JSONResponse({"detail": "Ya existe una receta con esta publicación de Instagram.",
                             "shortcode": str(e), "receta_id": existing["id"] if existing else None}, status_code=409)

    def get_or_404(rid: int) -> dict:
        r = svc.recipes.get(rid)
        if not r:
            raise HTTPException(404, "Receta no encontrada")
        return r

    # ------------------------------------------------------------ meta
    @app.get("/api/health", tags=["meta"])
    def health():
        return {"ok": True, "version": __version__}

    @app.get("/api/meta", tags=["meta"])
    def meta():
        all_r = svc.recipes.all()
        legacy = svc.db.get_meta("legacy_meta")
        import json as _j
        lm = _j.loads(legacy) if legacy else {}
        return {"version": __version__, "recetas": sum(r["tipo"] == "receta" for r in all_r),
                "solo_video": sum(r["tipo"] == "solo_video" for r in all_r),
                "con_video_local": sum(1 for r in all_r if r["media"]["video"]),
                "nota_precios": lm.get("nota_precios"), "generado": lm.get("generado"),
                "instagram_proveedor": svc.instagram.name, "ia_configurada": svc.ai.provider() is not None,
                "limites": {"foto_mb": st.max_photo_mb, "video_mb": st.max_video_mb}}

    # ------------------------------------------------------------ recipes
    @app.get("/api/recipes", tags=["recetas"])
    def list_recipes(q: str = "", tipo: Optional[Literal["receta", "solo_video"]] = None, etiqueta: Optional[str] = None,
                     max_min: Optional[int] = None, max_precio: Optional[float] = None, orden: str = "original",
                     estado: Optional[Literal["completa", "pendiente de transcribir"]] = None, favoritos: bool = False):
        return svc.recipes.search(q, tipo, etiqueta, max_min, max_precio, orden, estado, favoritos)

    @app.get("/api/tags", tags=["recetas"])
    def tags():
        return svc.recipes.tags()

    @app.get("/api/recipes/{rid}", tags=["recetas"])
    def get_recipe(rid: int):
        return get_or_404(rid)

    @app.post("/api/recipes", status_code=201, tags=["recetas"])
    def create_recipe(body: RecipeIn):
        return svc.recipes.create(body.model_dump(exclude_none=True))

    @app.put("/api/recipes/{rid}", tags=["recetas"])
    def update_recipe(rid: int, body: RecipeIn):
        get_or_404(rid)
        return svc.recipes.update(rid, body.model_dump(exclude_none=True))

    @app.patch("/api/recipes/{rid}", tags=["recetas"])
    def patch_recipe(rid: int, body: RecipePatch):
        get_or_404(rid)
        return svc.recipes.patch(rid, body.model_dump(exclude_none=True))

    @app.post("/api/recipes/{rid}/cocinado", status_code=201, tags=["recetas"])
    def add_cooked(rid: int, body: CookLog):
        get_or_404(rid)
        return svc.recipes.add_cook_log(rid, body.model_dump())

    @app.delete("/api/recipes/{rid}/cocinado/{idx}", tags=["recetas"])
    def del_cooked(rid: int, idx: int):
        get_or_404(rid)
        return svc.recipes.delete_cook_log(rid, idx)

    @app.delete("/api/recipes/{rid}", status_code=204, tags=["recetas"])
    def delete_recipe(rid: int):
        get_or_404(rid)
        svc.recipes.delete(rid)
        shutil.rmtree(st.media_dir / "recipes" / str(rid), ignore_errors=True)
        return Response(status_code=204)

    @app.post("/api/recipes/{rid}/media/{kind}", tags=["recetas"])
    async def upload_media(rid: int, kind: Literal["foto", "video"], file: UploadFile = File(...)):
        get_or_404(rid)
        limit = (st.max_photo_mb if kind == "foto" else st.max_video_mb) * 1024 * 1024
        allowed = PHOTO_TYPES if kind == "foto" else VIDEO_TYPES
        head = await file.read(16)
        ext = sniff(head)
        if ext not in allowed:
            raise HTTPException(415, f"Formato no admitido. Usa: {', '.join(allowed)}")
        dest_dir = st.media_dir / "recipes" / str(rid)
        dest_dir.mkdir(parents=True, exist_ok=True)
        size = len(head)
        fd, tmp = tempfile.mkstemp(dir=dest_dir, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(head)
                while chunk := await file.read(1 << 20):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, f"Archivo demasiado grande (máx. {limit // (1024 * 1024)} MB)")
                    out.write(chunk)
            for old in dest_dir.glob(f"{kind}.*"):
                old.unlink()
            final = dest_dir / f"{kind}.{ext}"
            os.replace(tmp, final)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        svc.recipes.set_media_field(rid, kind, f"media/recipes/{rid}/{kind}.{ext}")
        return svc.recipes.get(rid)

    @app.delete("/api/recipes/{rid}/media/{kind}", tags=["recetas"])
    def delete_media(rid: int, kind: Literal["foto", "video"]):
        r = get_or_404(rid)
        for old in (st.media_dir / "recipes" / str(rid)).glob(f"{kind}.*"):
            old.unlink()
        if r.get(kind):
            svc.recipes.set_media_field(rid, kind, None)
        return svc.recipes.get(rid)

    # ------------------------------------------------------------ export
    @app.post("/api/export", tags=["exportar"])
    def export(body: ExportRequest):
        recipes = svc.recipes.all()
        if body.ids is not None:
            wanted = set(body.ids)
            recipes = [r for r in recipes if r["id"] in wanted]
        if not recipes:
            raise HTTPException(400, "No hay recetas seleccionadas")
        content, mime, name = build_export(svc.recipes, recipes, body.formato, body.con_media)
        return Response(content, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})

    # ------------------------------------------------------------ instagram
    ig = svc.instagram

    @app.get("/api/sources", tags=["instagram"])
    def sources():
        from .services.sources import InstagramSource, list_sources
        return list_sources([InstagramSource(ig)])

    @app.get("/api/instagram/status", tags=["instagram"])
    def ig_status():
        return ig.status()

    @app.post("/api/instagram/login", tags=["instagram"])
    def ig_login(body: LoginIn):
        # The password is only passed through to the provider call; never stored or logged.
        res = ig.login(body.username.strip().lstrip("@"), body.password.get_secret_value())
        return {"estado": res.estado, "usuario": res.usuario, "mensaje": res.mensaje}

    @app.post("/api/instagram/2fa", tags=["instagram"])
    def ig_2fa(body: CodeIn):
        res = ig.two_factor(body.code)
        return {"estado": res.estado, "usuario": res.usuario}

    @app.post("/api/instagram/cookies", tags=["instagram"])
    def ig_cookies(body: CookiesIn):
        res = ig.login_with_cookies(body.sessionid.get_secret_value().strip(), body.cookies.get_secret_value())
        return {"estado": res.estado, "usuario": res.usuario}

    @app.post("/api/instagram/logout", tags=["instagram"])
    def ig_logout():
        ig.logout()
        return ig.status()

    @app.get("/api/instagram/collections", tags=["instagram"])
    def ig_collections():
        return [c.__dict__ for c in ig.collections()]

    @app.get("/api/instagram/collections/{cid}/posts", tags=["instagram"])
    def ig_posts(cid: str):
        recetas = svc.recipes.existing_shortcodes()
        drafts = svc.importer.draft_shortcodes()
        out = []
        for p in ig.posts(cid):
            d = p.public()
            d["estado"] = "importado" if p.shortcode in recetas else "borrador" if p.shortcode in drafts else "nuevo"
            out.append(d)
        return out

    @app.get("/api/instagram/thumb", tags=["instagram"])
    def ig_thumb(u: str):
        if not is_cdn_url(u):
            raise HTTPException(400, "URL no permitida")
        data, mime = ig.fetch_thumbnail(u)
        return Response(data, media_type=mime, headers={"Cache-Control": "max-age=86400"})

    @app.post("/api/instagram/import", status_code=202, tags=["instagram"])
    def ig_import(body: ImportIn):
        return svc.importer.start([i.model_dump() for i in body.items]).public()

    @app.get("/api/instagram/jobs/{jid}", tags=["instagram"])
    def ig_job(jid: str):
        job = svc.importer.jobs.get(jid)
        if not job:
            raise HTTPException(404, "Trabajo no encontrado")
        return job.public()

    @app.post("/api/instagram/jobs/{jid}/cancel", tags=["instagram"])
    def ig_job_cancel(jid: str):
        job = svc.importer.jobs.get(jid)
        if not job:
            raise HTTPException(404, "Trabajo no encontrado")
        job.cancelar = True
        return job.public()

    @app.get("/api/drafts", tags=["instagram"])
    def drafts():
        return svc.importer.drafts()

    @app.put("/api/drafts/{did}", tags=["instagram"])
    def update_draft(did: int, body: RecipeIn):
        d = svc.importer.update_draft(did, body.model_dump(exclude_none=True))
        if not d:
            raise HTTPException(404, "Borrador no encontrado")
        return d

    @app.post("/api/drafts/{did}/save", status_code=201, tags=["instagram"])
    def save_draft(did: int, body: Optional[RecipeIn] = None):
        try:
            return svc.importer.save_draft(did, body.model_dump(exclude_none=True) if body else None)
        except KeyError:
            raise HTTPException(404, "Borrador no encontrado") from None

    @app.delete("/api/drafts/{did}", status_code=204, tags=["instagram"])
    def delete_draft(did: int):
        if not svc.importer.delete_draft(did):
            raise HTTPException(404, "Borrador no encontrado")
        return Response(status_code=204)

    @app.post("/api/parse-caption", tags=["instagram"])
    def parse(body: CaptionIn):
        draft, metodo = svc.ai.extract_recipe(body.caption, autor=body.autor, video_url=body.video_url)
        return {"metodo": metodo, "receta": draft}

    # ------------------------------------------------------------ AI
    @app.get("/api/ai/config", tags=["ia"])
    def ai_config():
        return svc.ai.public_config()

    @app.put("/api/ai/config", tags=["ia"])
    def ai_save(body: AIConfigIn):
        return svc.ai.save_config(body.preset, body.base_url, body.model, body.api_key, body.enabled)

    @app.delete("/api/ai/config", status_code=204, tags=["ia"])
    def ai_delete():
        svc.ai.delete_config()
        return Response(status_code=204)

    @app.post("/api/ai/test", tags=["ia"])
    def ai_test():
        return svc.ai.test()

    def _recipe_from(body: AITransformIn) -> dict:
        if body.recipe is not None:
            return body.recipe
        if body.recipe_id is not None:
            return get_or_404(body.recipe_id)
        raise HTTPException(422, "Indica recipe_id o recipe")

    @app.post("/api/ai/translate", tags=["ia"])
    def ai_translate(body: AITransformIn):
        return svc.ai.translate(_recipe_from(body), body.lang)

    @app.post("/api/ai/estimate", tags=["ia"])
    def ai_estimate(body: AITransformIn):
        return svc.ai.estimate(_recipe_from(body))

    # ------------------------------------------------------------ tokens
    @app.get("/api/tokens", tags=["tokens"])
    def tokens_list():
        return svc.tokens.list()

    @app.post("/api/tokens", status_code=201, tags=["tokens"])
    def tokens_create(body: TokenCreate):
        return svc.tokens.create(body.name, list(body.scopes))

    @app.delete("/api/tokens/{tid}", tags=["tokens"])
    def tokens_revoke(tid: int):
        if not svc.tokens.revoke(tid):
            raise HTTPException(404, "Token no encontrado")
        return svc.tokens.get(tid)

    # ------------------------------------------------------------ external API v1 (token)
    def bearer(scope: str):
        def dep(authorization: str = Header(default="")) -> dict:
            info = svc.tokens.verify(authorization.removeprefix("Bearer ").strip(), scope)
            if not info:
                raise HTTPException(401, "Token de API ausente, inválido o sin permiso", headers={"WWW-Authenticate": "Bearer"})
            return info
        return dep

    read_dep, write_dep = Depends(bearer("read")), Depends(bearer("write"))

    @app.get("/api/v1/recipes", tags=["api externa (token)"], dependencies=[read_dep])
    def v1_search(q: str = "", etiqueta: Optional[str] = None, max_min: Optional[int] = None,
                  max_precio: Optional[float] = None, tipo: Optional[Literal["receta", "solo_video"]] = None,
                  limit: int = Query(50, ge=1, le=500)):
        """Busca recetas (texto en título/ingredientes/autor, etiqueta, tiempo y precio por ración máximos)."""
        return svc.recipes.search(q, tipo, etiqueta, max_min, max_precio)[:limit]

    @app.get("/api/v1/recipes/{rid}", tags=["api externa (token)"], dependencies=[read_dep])
    def v1_get(rid: int):
        r = get_or_404(rid)
        r.pop("caption_original", None)
        return r

    @app.get("/api/v1/collections", tags=["api externa (token)"], dependencies=[read_dep])
    def v1_collections():
        all_r = svc.recipes.all()
        return {"tipos": {"receta": sum(r["tipo"] == "receta" for r in all_r),
                          "solo_video": sum(r["tipo"] == "solo_video" for r in all_r)},
                "etiquetas": svc.recipes.tags()}

    @app.post("/api/v1/recipes", status_code=201, tags=["api externa (token)"], dependencies=[write_dep])
    def v1_create(body: RecipeIn):
        return svc.recipes.create(body.model_dump(exclude_none=True), origen="api")

    @app.post("/api/v1/recipes/import-url", status_code=201, tags=["api externa (token)"], dependencies=[write_dep])
    def v1_import_url(body: ImportUrlIn):
        """Importa una publicación de Instagram por URL (requiere Instagram conectado en la web)."""
        return svc.importer.import_url(body.url)

    # ------------------------------------------------------------ static + media + MCP
    app.mount("/mcp", BearerAuthASGI(mcp_app, lambda t: svc.tokens.verify(t, "read")))
    app.mount("/videos", StaticFiles(directory=st.videos_dir, check_dir=False), name="videos")
    app.mount("/media", StaticFiles(directory=st.media_dir, check_dir=False), name="media")
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app
