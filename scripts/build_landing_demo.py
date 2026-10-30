#!/usr/bin/env python3
"""Build landing/demo/: the real web app UI (static/) running against an in-browser mock API.

The hero simulators on the landing embed this copy so they show the actual screens, components and flows
of Recetario C (list, detail with servings scaler, planner, shopping list, settings, mobile tab bar).
Responses are recorded from the real FastAPI app with the invented sample data (data/sample) in a throwaway
temp dir: no session, keys, private seed, videos or Instagram content. Writes stay in memory (nothing is saved).

Run: python scripts/build_landing_demo.py   (needs the app requirements; re-run after changing static/ or data/sample)
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "landing" / "demo"
sys.path.insert(0, str(ROOT))

# Mon..Fri, lunch/dinner: (recipe photo slug, servings)
PLAN = [("lentejas-estofadas", "tortilla-de-patatas"), ("crema-de-calabaza", "pescado-al-horno"),
        ("macarrones-con-tomate", "salmorejo"), ("pollo-asado", "ensalada-de-garbanzos"), ("paella", "croquetas")]
PANTRY = ["sal", "aceite de oliva", "pimienta negra"]


def record():
    tmp = tempfile.mkdtemp()
    for k in ("RECETAS_DATA_DIR", "RECETAS_MEDIA_DIR", "RECETAS_SECRET_DIR", "RECETAS_VIDEOS_DIR"):
        os.environ[k] = str(Path(tmp) / k.lower())
    os.environ["RECETAS_IG_PROVIDER"] = "mock"
    os.environ["RECETAS_SEED_FILE"] = str(ROOT / "data" / "sample" / "recetas-demo.json")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    get = {}
    with TestClient(app) as c:
        c.headers["X-CSRF-Token"] = c.post("/api/auth/setup", json={"username": "demo", "password": "demo-landing-build"}).json()["csrf"]
        rs = c.get("/api/recipes").json()
        by = {Path(r.get("foto") or "").stem: r for r in rs}
        wk = c.get("/api/plan").json()
        for d, pair in zip(wk["dias"], PLAN):
            for comida, s in zip(("comida", "cena"), pair):
                c.post("/api/plan", json={"fecha": d, "comida": comida, "receta_id": by[s]["id"]}).raise_for_status()
        lid = c.post("/api/compra/listas", json={"nombre": "Semana"}).json()["id"]
        c.post("/api/plan/a-lista", json={"lista_id": lid, "inicio": wk["inicio"], "fin": wk["fin"]}).raise_for_status()
        for n in PANTRY:
            c.post("/api/compra/despensa", json={"nombre": n})
        for p in ["/api/auth/me", "/api/meta", "/api/recipes", "/api/tags", "/api/preferencias/lista", "/api/plan",
                  "/api/compra/listas", f"/api/compra/listas/{lid}", "/api/compra/categorias", "/api/compra/despensa",
                  "/api/ajustes/portada", "/api/portadas/biblioteca", "/api/estado", "/api/acceso", "/api/ai/config",
                  "/api/tokens", "/api/instagram/status", "/api/drafts", "/api/sources"]:
            r = c.get(p)
            if r.status_code == 200:
                get[p] = r.json()
        for r in rs:
            get[f"/api/recipes/{r['id']}"] = c.get(f"/api/recipes/{r['id']}").json()
            for n in range(1, 13):
                get[f"/api/recipes/{r['id']}/escalar?raciones={n}"] = c.get(f"/api/recipes/{r['id']}/escalar?raciones={n}").json()
        meta = get["/api/meta"]
    app.state.services.db.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return get, meta, lid


def sanitize(get):
    get["/api/auth/me"] = {"autenticado": True, "usuario": "demo", "csrf": "demo"}
    get["/api/meta"].update(instagram_proveedor=None, ia_configurada=False)
    s = json.dumps(get, ensure_ascii=False)
    s = re.sub(r'"/tmp/[^"]*?/recetas_(\w+?)_dir"', lambda m: json.dumps("/srv/recetario/" + m.group(1)), s)
    get = json.loads(s)
    if "/api/acceso" in get:
        get["/api/acceso"].update(urls=[{"url": "http://192.168.1.20:8088/", "tipo": "lan"}, {"url": "http://localhost:8088/", "tipo": "local"}],
                                  archivo_config=".env")
    get.get("/api/ai/config", {}).update(enabled=False, configurado=False)
    get["/api/instagram/status"] = {"conectado": False, "usuario": None, "proveedor": None}

    def covers(o):  # only the CC0 sample covers, re-encoded as WebP under demo/media/covers
        if isinstance(o, dict): return {k: covers(v) for k, v in o.items()}
        if isinstance(o, list): return [covers(v) for v in o]
        if isinstance(o, str) and re.fullmatch(r"/?media/covers/[\w-]+\.jpg", o):
            return "media/covers/" + Path(o).stem + ".webp"
        return o
    get = covers(get)
    for k in [k for k in get if re.fullmatch(r"/api/recipes(/\d+)?", k)]:
        for r in (get[k] if isinstance(get[k], list) else [get[k]]):
            r.update(video_url=None, shortcode=None)
            r.pop("miniatura", None)
            r["media"] = {"video": None, "foto": r.get("foto"), "miniatura": None}
            r["portada"] = r["portada_efectiva"] = r.get("foto")
    return get


def main():
    get, meta, lid = record()
    get = sanitize(get)
    if OUT.exists(): shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT, ignore=shutil.ignore_patterns("index.html"))
    (OUT / "media" / "covers").mkdir(parents=True)
    for f in sorted((ROOT / "data" / "sample" / "covers").glob("*.jpg")):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-vf", "scale=640:-2", "-c:v", "libwebp", "-quality", "72",
                        str(OUT / "media" / "covers" / (f.stem + ".webp"))], check=True)
    (OUT / "data").mkdir()
    (OUT / "data" / "api.json").write_text(json.dumps({"get": get, "lista": lid, "built": dt.date.today().isoformat()},
                                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    html = re.sub(r"<script>\(function\(\)\{var t=localStorage.*?</script>", '<script src="boot.js"></script>', html, flags=re.S)
    html = re.sub(r'<link rel="icon" href="data:[^"]*">', '<link rel="icon" href="/favicon.svg" type="image/svg+xml">', html)
    html = html.replace('<meta name="viewport"', '<meta name="robots" content="noindex">\n<meta name="viewport"', 1)
    html = re.sub(r'(src|href)="/assets/', r'\1="assets/', html)
    html = html.replace('<script src="assets/api.js"></script>', '<script src="mock-api.js"></script>\n<script src="assets/api.js"></script>', 1)
    assert "boot.js" in html and "mock-api.js" in html
    (OUT / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(ROOT / "scripts" / "landing_demo" / "boot.js", OUT / "boot.js")
    shutil.copy(ROOT / "scripts" / "landing_demo" / "mock-api.js", OUT / "mock-api.js")
    print(f"landing demo: {OUT} ({len(get['/api/recipes'])} recetas, {len(get)} respuestas)")


if __name__ == "__main__":
    main()
