"""Take UI screenshots with Playwright against a running server (use --mock-instagram).

    python scripts/screenshots.py --base http://127.0.0.1:8088 --recipe 9
Writes docs/screenshots/{view}-{theme}-{desktop|mobile}.png

Every recipe cover is set to a CC0 photo from data/sample/covers before shooting (no frames from real
videos). The optional frame-slider shot needs --private-video PATH (uploaded to --recipe, removed afterwards); it is written as editor-portada-fotograma-private.png and must never be used in
the landing page or the static demo.
"""
import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SIZES = {"desktop": (1440, 900), "mobile": (390, 844)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8088")
    ap.add_argument("--recipe", type=int, default=10)
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="contraseña-capturas")
    ap.add_argument("--private-video", default=None, help="real video for the *-private.png frame-slider shot")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        # context locale formats JS dates; native <input type=date> follows the process LANG, so set both
        b = p.chromium.launch(args=["--lang=es-ES"], env={**os.environ, "LANG": "es_ES.UTF-8", "LANGUAGE": "es_ES:es"})
        creds = {"username": a.user, "password": a.password}
        for theme in ("light", "dark"):
            for size, (w, h) in SIZES.items():
                ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="es-ES",
                                    color_scheme=theme)
                ctx.add_init_script(f"localStorage.setItem('tema','{theme}');")
                pg = ctx.new_page()
                pg.on("pageerror", lambda e: errors.append(str(e)))
                shot = lambda name, full=False: pg.screenshot(path=str(OUT / f"{name}-{theme}-{size}.png"), full_page=full)
                # login screen (fresh context, no session); create the admin first: python -m app.cli create-admin
                pg.goto(f"{a.base}/#/recetas"); pg.wait_for_selector("#lf"); pg.wait_for_timeout(200); shot("login")
                pg.fill("#lu", a.user); pg.fill("#lp", a.password); pg.click("#lf button[type=submit]")
                pg.wait_for_selector(".card")
                csrf = pg.evaluate("fetch('/api/auth/me').then(r => r.json()).then(m => m.csrf)")
                H = {"X-CSRF-Token": csrf}
                if theme == "light" and size == "desktop":
                    use_library_covers(pg, a.base, H)
                pg.goto(f"{a.base}/#/recetas"); pg.wait_for_selector(".card"); pg.wait_for_timeout(300); shot("lista")
                # filters popover (desktop) / sheet (mobile) with one active filter so the badge shows
                pg.click("#filtBtn"); pg.select_option("#tmax", "45"); pg.wait_for_timeout(400); shot("filtros")
                pg.click("#filtReset"); pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
                for mode in ("una", "compacta", "miniatura", "cuadricula"):
                    pg.click(f'[data-view="{mode}"]'); pg.wait_for_timeout(500); shot(f"lista-{mode}")
                pg.fill("#densR", "6"); pg.dispatch_event("#densR", "input"); pg.wait_for_timeout(500); shot("lista-cuadricula-densa")
                pg.fill("#densR", "4"); pg.dispatch_event("#densR", "input"); pg.wait_for_timeout(500)
                pg.goto(f"{a.base}/#/receta/{a.recipe}"); pg.wait_for_selector(".ings li"); pg.wait_for_timeout(500); shot("detalle")
                pg.evaluate("document.querySelector('#dDate')?.scrollIntoView({block:'center'})"); shot("detalle-fecha")
                pg.goto(f"{a.base}/#/editar/{a.recipe}"); pg.wait_for_selector("#coverPicker")
                pg.click('#coverPicker input[value="generic"]', force=True); pg.wait_for_selector("#cpLib .lib-item")
                pg.evaluate("document.querySelector('#coverPicker').scrollIntoView()"); pg.wait_for_timeout(600)
                shot("editor-portada")
                pg.goto(f"{a.base}/#/recetas"); pg.wait_for_selector(".card")
                pg.click("#expBtn"); pg.wait_for_selector("dialog[open]"); pg.wait_for_timeout(200); shot("exportar")
                pg.keyboard.press("Escape")
                # import wizard: login with the mock provider, open a collection, select posts
                pg.request.post(f"{a.base}/api/instagram/login", data={"username": "demo", "password": "demo"}, headers=H)
                pg.goto(f"{a.base}/#/importar"); pg.wait_for_selector("#wz, .wizard")
                pg.evaluate("W.step = 3; W.coll = {id: 'C', nombre: 'Recetas'}; W.pick.clear(); viewImport()")
                pg.wait_for_selector(".post")
                pg.click("#all"); pg.wait_for_timeout(300); shot("importar")
                pg.goto(f"{a.base}/#/ajustes/ia"); pg.wait_for_selector("#aiF"); pg.wait_for_timeout(300); shot("ajustes")
                pg.wait_for_selector("#s-estado .stats"); pg.evaluate("document.querySelector('#s-estado').scrollIntoView()")
                pg.wait_for_timeout(300); shot("estado")
                pg.evaluate("document.querySelector('#s-acc').scrollIntoView()"); pg.wait_for_selector("#s-acc form")
                pg.click("#s-acc [data-qr]"); pg.wait_for_timeout(400); shot("acceso")
                pg.goto(f"{a.base}/#/planificador"); pg.wait_for_selector(".week"); pg.wait_for_timeout(400); shot("planificador")
                pg.goto(f"{a.base}/#/compra"); pg.wait_for_selector(".shop"); pg.wait_for_timeout(400); shot("compra")
                ctx.close()
        if a.private_video:
            private_frame_shot(b, a)
        b.close()
    print("page errors:", errors or "none")
    overview()


def use_library_covers(pg, base, H):
    """Point every recipe at a CC0 library photo so no screenshot shows a frame from a real video."""
    lib = pg.request.get(f"{base}/api/portadas/biblioteca").json()
    ids = [x["id"] for x in lib]
    recs = pg.request.get(f"{base}/api/recipes?limit=500").json()
    items = recs.get("items", recs) if isinstance(recs, dict) else recs
    # every sample recipe ships its own distinct CC0 photo (data/sample/recetas-demo.json "foto"); use exactly that one
    sample = json.loads((Path(__file__).resolve().parent.parent / "data/sample/recetas-demo.json").read_text(encoding="utf-8"))
    sample = sample.get("recetas", sample) if isinstance(sample, dict) else sample
    by_title = {x["titulo"]: Path(x["foto"]).stem for x in sample}
    for i, r in enumerate(items):
        stem = by_title.get(r.get("titulo"), "")
        pick = stem if stem in ids else ids[i % len(ids)]
        pg.request.put(f"{base}/api/recipes/{r['id']}/portada", headers=H,
                       data={"fuente": "generic", "biblioteca": pick})
    pg.request.put(f"{base}/api/ajustes/portada", headers=H, data={"predeterminada": "generic"})


def private_frame_shot(b, a):
    """Frame-slider shot from a real (private) video: *-private.png, kept out of landing/demo."""
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="es-ES", color_scheme="light")
    pg = ctx.new_page()
    pg.goto(f"{a.base}/#/recetas"); pg.wait_for_selector("#lf")
    pg.fill("#lu", a.user); pg.fill("#lp", a.password); pg.click("#lf button[type=submit]"); pg.wait_for_selector(".card")
    csrf = pg.evaluate("fetch('/api/auth/me').then(r => r.json()).then(m => m.csrf)")
    H = {"X-CSRF-Token": csrf}
    v = Path(a.private_video)
    pg.request.post(f"{a.base}/api/recipes/{a.recipe}/media/video", headers=H,
                    multipart={"file": {"name": v.name, "mimeType": "video/mp4", "buffer": v.read_bytes()}})
    pg.goto(f"{a.base}/#/editar/{a.recipe}"); pg.wait_for_selector("#coverPicker")
    pg.click('#coverPicker input[value="frame"]', force=True)
    pg.fill("#cpT", "4"); pg.dispatch_event("#cpT", "input")
    pg.wait_for_function("document.querySelector('#cpFrame').src.startsWith('blob:')")
    pg.evaluate("document.querySelector('#coverPicker').scrollIntoView()"); pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "editor-portada-fotograma-private.png"))
    pg.request.delete(f"{a.base}/api/recipes/{a.recipe}/media/video", headers=H)  # don't leave it in the demo data
    ctx.close()


def overview():
    """Contact sheet of every screenshot: docs/screenshots/_overview.png (needs ffmpeg)."""
    import shutil
    import subprocess
    import tempfile
    files = sorted(f for f in OUT.glob("*.png") if not f.name.startswith("_") and "-private" not in f.name)
    if not files or not shutil.which("ffmpeg"):
        return
    cols = 6
    with tempfile.TemporaryDirectory() as tmp:
        # every tile 360x225 letterboxed on a neutral background, labelled with its file name
        for i, f in enumerate(files):
            label = f.stem.replace(":", "")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(f), "-vf",
                            "scale=360:225:force_original_aspect_ratio=decrease,pad=360:250:(ow-iw)/2:0:color=0xe9e4dc,"
                            f"drawtext=text='{label}':x=6:y=232:fontsize=13:fontcolor=0x333333",
                            f"{tmp}/{i:03d}.png"], check=True)
        rows = -(-len(files) // cols)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "1", "-i", f"{tmp}/%03d.png", "-vf",
                        f"tile={cols}x{rows}:padding=6:margin=6:color=0xffffff", "-frames:v", "1",
                        str(OUT / "_overview.png")], check=True)
    print("overview:", OUT / "_overview.png", f"({len(files)} capturas)")


if __name__ == "__main__":
    main()
