#!/usr/bin/env python3
"""Screenshots of landing/ (ES/EN × light/dark × desktop/mobile, full page) into landing/docs/screenshots/.
Serves landing/ on a local port with http.server; nothing leaves the machine."""
import functools, http.server, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "landing/docs/screenshots"; OUT.mkdir(parents=True, exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Quiet, directory=str(ROOT / "landing"))
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_port}"
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for lang, path in (("es", "/"), ("en", "/en/")):
        for theme in ("light", "dark"):
            for dev, vp, scale in (("desktop", (1440, 900), 1), ("mobile", (390, 844), 1)):
                ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=scale, color_scheme=theme)
                pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.goto(base + path, wait_until="networkidle")
                pg.evaluate("""async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { scrollTo({top: y, behavior: 'instant'}); await new Promise(r => setTimeout(r, 60)); } scrollTo({top: 0, behavior: 'instant'}); await new Promise(r => setTimeout(r, 200));
                  for (const i of document.images) { i.loading = 'eager'; } 
                  await Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; }))); }""")
                pg.screenshot(path=str(OUT / f"landing-{lang}-{theme}-{dev}.png"), full_page=True)
                pg.screenshot(path=str(OUT / f"landing-{lang}-{theme}-{dev}-hero.png"))
                ctx.close()
    # toggle check: system light, click -> dark persisted in localStorage
    ctx = b.new_context(color_scheme="light"); pg = ctx.new_page(); pg.goto(base + "/")
    pg.click("#themeBtn"); pg.reload()
    assert pg.evaluate("document.documentElement.dataset.theme") == "dark", "toggle not persisted"
    b.close()
srv.shutdown()
print("page errors:", errors or "none"); print("saved to", OUT)
