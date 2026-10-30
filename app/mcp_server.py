"""MCP server (official Python SDK) exposing the recipe book to AI agents.

* Streamable HTTP, mounted by the web app under ``/mcp`` (Bearer token required).
* stdio: ``python -m app.mcp_stdio`` with ``RECETAS_API_TOKEN`` set.

Read tools need a token with the ``read`` scope; ``import_recipe`` needs ``write``.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver import Context, MCPServer

from .models import RecipeIn
from .services.instagram import InstagramError
from .services.recipes import DuplicateError


def _summary(r: dict) -> dict:
    return {k: r.get(k) for k in ("id", "tipo", "titulo", "autor", "tiempo_total_min", "precio_racion_eur",
                                  "raciones", "etiquetas", "video_url")}


def build_mcp(services: Any, stdio_token: Optional[dict] = None) -> MCPServer:
    mcp = MCPServer(
        name="recetario-c",
        instructions="Recetario personal (recetas de Instagram). Los precios son estimaciones. "
                     "Usa search_recipes para buscar y get_recipe para el detalle.",
    )

    def token_info(ctx: Context) -> Optional[dict]:
        if stdio_token is not None:
            return stdio_token
        headers = ctx.headers or {}
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        return services.tokens.verify(auth.removeprefix("Bearer ").strip(), "read") if auth else None

    def require(ctx: Context, scope: str) -> None:
        info = token_info(ctx)
        if not info or scope not in info["scopes"]:
            raise ToolError(f"Token sin permiso '{scope}'")

    @mcp.tool()
    def search_recipes(ctx: Context, query: str = "", tag: str = "", max_minutes: Optional[int] = None,
                       max_price_per_serving: Optional[float] = None, include_video_only: bool = False,
                       limit: int = 20) -> list[dict]:
        """Busca recetas por texto (título, ingrediente, autor), etiqueta, tiempo máximo y precio/ración máximo."""
        require(ctx, "read")
        res = services.recipes.search(q=query, tipo=None if include_video_only else "receta", etiqueta=tag or None,
                                      max_min=max_minutes, max_precio=max_price_per_serving)
        return [_summary(r) for r in res[: max(1, min(limit, 100))]]

    @mcp.tool()
    def get_recipe(ctx: Context, recipe_id: int) -> dict:
        """Devuelve una receta completa (ingredientes con cantidades y precio estimado, pasos con minutos)."""
        require(ctx, "read")
        r = services.recipes.get(recipe_id)
        if not r:
            raise ValueError("Receta no encontrada")
        r.pop("caption_original", None)
        return r

    @mcp.tool()
    def list_collections(ctx: Context) -> dict:
        """Lista las colecciones del recetario: tipos (recetas / solo vídeo) y etiquetas con su número de recetas."""
        require(ctx, "read")
        all_r = services.recipes.all()
        return {"tipos": {"receta": sum(r["tipo"] == "receta" for r in all_r),
                          "solo_video": sum(r["tipo"] == "solo_video" for r in all_r)},
                "etiquetas": services.recipes.tags()}

    @mcp.tool()
    def import_recipe(ctx: Context, recipe_json: str = "", instagram_url: str = "") -> dict:
        """Importa una receta: o bien un JSON con el esquema del recetario (titulo, ingredientes, pasos...),
        o bien la URL de una publicación de Instagram (requiere Instagram conectado en la web). Necesita scope 'write'."""
        require(ctx, "write")
        try:
            if instagram_url:
                r = services.importer.import_url(instagram_url)
            elif recipe_json:
                payload = RecipeIn.model_validate(json.loads(recipe_json)).model_dump(exclude_none=True)
                r = services.recipes.create(payload, origen="mcp")
            else:
                raise ValueError("Indica recipe_json o instagram_url")
        except DuplicateError as e:
            raise ValueError(f"Ya existe una receta con el código {e}") from None
        except InstagramError as e:
            raise ValueError(str(e)) from None
        return _summary(r)

    return mcp


class BearerAuthASGI:
    """Rejects MCP HTTP requests without a valid (non-revoked) read token."""

    def __init__(self, app: Callable, verify: Callable[[str], Optional[dict]]):
        self.app, self.verify = app, verify

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            token = headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not self.verify(token):
                body = b'{"error":"Token de API ausente o no valido"}'
                await send({"type": "http.response.start", "status": 401, "headers": [
                    (b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
