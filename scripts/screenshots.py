"""Take UI screenshots with Playwright against a running server (use --mock-instagram).

    python scripts/screenshots.py --base http://127.0.0.1:8088 --recipe 9
Writes docs/screenshots/{view}-{theme}-{desktop|mobile}.png
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SIZES = {"desktop": (1440, 900), "mobile": (390, 844)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8088")
    ap.add_argument("--recipe", type=int, default=9)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for theme in ("light", "dark"):
            for size, (w, h) in SIZES.items():
                ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="es-ES",
                                    color_scheme=theme)
                ctx.add_init_script(f"localStorage.setItem('tema','{theme}');")
                pg = ctx.new_page()
                pg.on("pageerror", lambda e: errors.append(str(e)))
                shot = lambda name: pg.screenshot(path=str(OUT / f"{name}-{theme}-{size}.png"))
                pg.goto(f"{a.base}/#/recetas"); pg.wait_for_selector(".card"); pg.wait_for_timeout(300); shot("lista")
                pg.goto(f"{a.base}/#/receta/{a.recipe}"); pg.wait_for_selector(".ings li"); pg.wait_for_timeout(500); shot("detalle")
                pg.goto(f"{a.base}/#/recetas"); pg.wait_for_selector(".card")
                pg.click("#expBtn"); pg.wait_for_selector("dialog[open]"); pg.wait_for_timeout(200); shot("exportar")
                pg.keyboard.press("Escape")
                # import wizard: login with the mock provider, open a collection, select posts
                pg.request.post(f"{a.base}/api/instagram/login", data={"username": "demo", "password": "demo"})
                pg.goto(f"{a.base}/#/importar"); pg.wait_for_selector("#wz, .wizard")
                pg.evaluate("W.step = 3; W.coll = {id: 'C', nombre: 'Recetas'}; W.pick.clear(); viewImport()")
                pg.wait_for_selector(".post")
                pg.click("#all"); pg.wait_for_timeout(300); shot("importar")
                pg.goto(f"{a.base}/#/ajustes"); pg.wait_for_selector("#aiF"); pg.wait_for_timeout(300); shot("ajustes")
                ctx.close()
        b.close()
    print("page errors:", errors or "none")


if __name__ == "__main__":
    main()
