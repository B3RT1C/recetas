"""Build a read-only static demo of the UI into dist/ (no backend, no media, no secrets).

    python scripts/build_static.py [--out dist]
Recipes come from the invented sample data in data/sample (never the private seed); video/photo paths and Instagram thumbnails are stripped.
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


def _utf8_console() -> None:
    # Windows consoles default to cp1252/cp850: never crash on non-ASCII output
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _force_remove(func, path, _exc):
    os.chmod(path, 0o700)  # read-only files (e.g. copied from a git checkout) on Windows
    func(path)


def main():
    _utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    out = Path(ap.parse_args().out)
    # ignore_cleanup_errors: on Windows a just-closed SQLite/WAL file can still be locked for a moment
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for k in ("RECETAS_DATA_DIR", "RECETAS_MEDIA_DIR", "RECETAS_SECRET_DIR", "RECETAS_VIDEOS_DIR"):
            os.environ[k] = str(Path(tmp) / k.lower())
        os.environ["RECETAS_IG_PROVIDER"] = "mock"
        # sample data only: the real seed contains third-party creators' captions and handles
        os.environ["RECETAS_SEED_FILE"] = str(ROOT / "data" / "sample" / "recetas-demo.json")
        from fastapi.testclient import TestClient
        from app.main import create_app
        app = create_app()
        with TestClient(app) as c:
            # the UI API needs a session: create a throwaway admin in the temp data dir
            csrf = c.post("/api/auth/setup", json={"username": "demo", "password": "demo-static-build"}).json()["csrf"]
            c.headers["X-CSRF-Token"] = csrf
            recetas = c.get("/api/recipes").json()
            meta = c.get("/api/meta").json()
        # release the SQLite handle before the temp dir is removed (Windows can't delete open files)
        app.state.services.db.close()
    sample = {r["titulo"]: r.get("foto") for r in json.loads(
        (ROOT / "data" / "sample" / "recetas-demo.json").read_text(encoding="utf-8"))["recetas"]}
    for r in recetas:
        # only the free sample covers (data/sample/covers, CC0/PD) are shipped; never videos or Instagram frames
        foto = sample.get(r.get("titulo"))
        foto = foto if foto and (ROOT / "data" / "sample" / "covers" / Path(foto).name).exists() else None
        r["media"] = {"video": None, "foto": foto}
        r.pop("miniatura", None)
        r["portada"] = foto
    meta.update(instagram_proveedor=None, ia_configurada=False)
    if out.exists():
        shutil.rmtree(out, onexc=_force_remove) if sys.version_info >= (3, 12) else shutil.rmtree(out)
    shutil.copytree(ROOT / "static", out)
    shutil.copytree(ROOT / "data" / "sample" / "covers", out / "media" / "covers")
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
