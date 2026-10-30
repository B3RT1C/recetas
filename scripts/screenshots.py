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
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="contraseña-capturas")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
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
                pg.goto(f"{a.base}/#/recetas"); pg.wait_for_selector(".card"); pg.wait_for_timeout(300); shot("lista")
                for mode in ("una", "info", "detalle", "cuadricula"):
                    pg.click(f'[data-view="{mode}"]'); pg.wait_for_timeout(500); shot(f"lista-{mode}")
                pg.fill("#densR", "6"); pg.dispatch_event("#densR", "input"); pg.wait_for_timeout(500); shot("lista-cuadricula-densa")
                pg.fill("#densR", "4"); pg.dispatch_event("#densR", "input"); pg.wait_for_timeout(500)
                pg.goto(f"{a.base}/#/receta/{a.recipe}"); pg.wait_for_selector(".ings li"); pg.wait_for_timeout(500); shot("detalle")
                pg.goto(f"{a.base}/#/recetas"); pg.wait_for_selector(".card")
                pg.click("#expBtn"); pg.wait_for_selector("dialog[open]"); pg.wait_for_timeout(200); shot("exportar")
                pg.keyboard.press("Escape")
                # import wizard: login with the mock provider, open a collection, select posts
                pg.request.post(f"{a.base}/api/instagram/login", data={"username": "demo", "password": "demo"}, headers=H)
                pg.goto(f"{a.base}/#/importar"); pg.wait_for_selector("#wz, .wizard")
                pg.evaluate("W.step = 3; W.coll = {id: 'C', nombre: 'Recetas'}; W.pick.clear(); viewImport()")
                pg.wait_for_selector(".post")
                pg.click("#all"); pg.wait_for_timeout(300); shot("importar")
                pg.goto(f"{a.base}/#/ajustes"); pg.wait_for_selector("#aiF"); pg.wait_for_timeout(300); shot("ajustes")
                pg.wait_for_selector("#s-estado .stats"); pg.evaluate("document.querySelector('#s-estado').scrollIntoView()")
                pg.wait_for_timeout(300); shot("estado")
                pg.evaluate("document.querySelector('#s-acc').scrollIntoView()"); pg.wait_for_selector("#s-acc form")
                pg.click("#s-acc [data-qr]"); pg.wait_for_timeout(400); shot("acceso")
                pg.goto(f"{a.base}/#/planificador"); pg.wait_for_selector(".week"); pg.wait_for_timeout(400); shot("planificador")
                pg.goto(f"{a.base}/#/compra"); pg.wait_for_selector(".shop"); pg.wait_for_timeout(400); shot("compra")
                ctx.close()
        b.close()
    print("page errors:", errors or "none")


if __name__ == "__main__":
    main()
