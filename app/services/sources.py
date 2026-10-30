"""Pluggable recipe sources. The import wizard is source-agnostic: it asks the
registry for sources, then for collections -> items -> import (video/foto/ambos).

Implemented now: 'instagram' (wraps InstagramProvider). Planned: tiktok,
youtube_shorts, pinterest and 'web' (any recipe URL: schema.org Recipe JSON-LD,
fallback to AI / heuristic extractor)."""
from __future__ import annotations

from typing import Protocol

from .instagram import IGCollection, IGPost, InstagramProvider


class RecipeSource(Protocol):
    id: str
    label: str
    needs_login: bool

    def status(self) -> dict: ...
    def collections(self) -> list[IGCollection]: ...      # generic: id, nombre, total, portada
    def items(self, collection_id: str) -> list[IGPost]: ...  # generic item: shortcode(=item id), url, autor, caption, miniatura
    def item(self, item_id: str) -> IGPost: ...
    def download(self, item: IGPost, kind: str, dest) -> object: ...


class InstagramSource:
    id, label, needs_login = "instagram", "Instagram (guardados)", True

    def __init__(self, provider: InstagramProvider):
        self.p = provider

    def status(self): return self.p.status()
    def collections(self): return self.p.collections()
    def items(self, cid): return self.p.posts(cid)
    def item(self, item_id): return self.p.post(item_id)
    def download(self, item, kind, dest): return self.p.download(item, kind, dest)


PLANNED = [
    {"id": "tiktok", "label": "TikTok", "disponible": False},
    {"id": "youtube_shorts", "label": "YouTube Shorts", "disponible": False},
    {"id": "pinterest", "label": "Pinterest", "disponible": False},
    {"id": "web", "label": "Cualquier web de recetas (URL)", "disponible": False},
]


def list_sources(sources: list[RecipeSource]) -> list[dict]:
    return [{"id": s.id, "label": s.label, "disponible": True, "requiere_login": s.needs_login} for s in sources] + PLANNED
