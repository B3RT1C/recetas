"""Cache-busting for /assets: versioned URLs in index.html plus matching Cache-Control headers."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from . import __version__

IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"
_ASSET_RE = re.compile(r'(["\'])/assets/([A-Za-z0-9_.\-/]+?)(\?[^"\']*)?\1')


def asset_versions(directory: Path) -> dict[str, str]:
    """Map each file under directory (posix relative path) to '<app version>-<8 hex of sha256>'."""
    out = {}
    for p in sorted(Path(directory).rglob("*")):
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:8]
            out[p.relative_to(directory).as_posix()] = f"{__version__}-{h}"
    return out


def version_html(html: str, versions: dict[str, str]) -> str:
    def sub(m):
        q, name = m.group(1), m.group(2)
        v = versions.get(name)
        return f"{q}/assets/{name}?v={v}{q}" if v else m.group(0)
    return _ASSET_RE.sub(sub, html)


class VersionedStaticFiles(StaticFiles):
    """Immutable caching only for the exact current ?v=; everything else revalidates (ETag/Last-Modified)."""

    def __init__(self, *, directory: Path, **kw):
        super().__init__(directory=directory, **kw)
        self.versions = asset_versions(Path(directory))

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if resp.status_code in (200, 304):
            qs = dict(p.split("=", 1) for p in scope.get("query_string", b"").decode().split("&") if "=" in p)
            want = self.versions.get(path.replace("\\", "/"))
            resp.headers["Cache-Control"] = IMMUTABLE if want and qs.get("v") == want else REVALIDATE
        return resp
