"""Build a read-only static demo of the UI into dist/ (no backend, no media, no secrets).

    python scripts/build_static.py [--out dist]
Recipes come from the bundled seed data; video/photo paths and Instagram thumbnails are stripped.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    out = Path(ap.parse_args().out)
    with tempfile.TemporaryDirectory() as tmp:
        for k in ("RECETAS_DATA_DIR", "RECETAS_MEDIA_DIR", "RECETAS_SECRET_DIR", "RECETAS_VIDEOS_DIR"):
            os.environ[k] = str(Path(tmp) / k.lower())
        os.environ["RECETAS_IG_PROVIDER"] = "mock"
        from fastapi.testclient import TestClient
        from app.main import create_app
        with TestClient(create_app()) as c:
            # the UI API needs a session: create a throwaway admin in the temp data dir
            csrf = c.post("/api/auth/setup", json={"username": "demo", "password": "demo-static-build"}).json()["csrf"]
            c.headers["X-CSRF-Token"] = csrf
            recetas = c.get("/api/recipes").json()
            meta = c.get("/api/meta").json()
    for r in recetas:
        r["media"] = {"video": None, "foto": None}
        r.pop("miniatura", None)
        r["portada"] = None
    meta.update(instagram_proveedor=None, ia_configurada=False)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "static", out)
    idx = out / "index.html"
    html = idx.read_text(encoding="utf-8")
    html = html.replace('data-mode="server"', 'data-mode="static"', 1)
    html = re.sub(r'(src|href)="/assets/', r'\1="assets/', html)
    idx.write_text(html, encoding="utf-8")
    (out / "data").mkdir(exist_ok=True)
    (out / "data" / "recipes.json").write_text(json.dumps({"meta": meta, "recetas": recetas}, ensure_ascii=False),
                                               encoding="utf-8")
    print(f"static demo: {out} ({len(recetas)} recetas)")


if __name__ == "__main__":
    main()
