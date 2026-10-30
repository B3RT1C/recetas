"""Browser checks of the list view picker at a 360 px viewport (skipped when Playwright/Chromium is missing)."""
import pytest

from tests.conftest import ADMIN
from tests.test_tokens_and_mcp import server  # noqa: F401  (live uvicorn fixture)

pw = pytest.importorskip("playwright.sync_api")

VIEWS = ("una", "compacta", "miniatura", "cuadricula")


@pytest.fixture()
def page(server, services):  # noqa: F811
    services.auth.create_admin(*ADMIN)
    try:
        p = pw.sync_playwright().start()
        b = p.chromium.launch()
    except Exception as e:  # pragma: no cover
        pytest.skip(f"chromium not available: {e}")
    ctx = b.new_context(viewport={"width": 360, "height": 800}, locale="es-ES", has_touch=True)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{server}/#/recetas"); pg.wait_for_selector("#lf")
    pg.fill("#lu", ADMIN[0]); pg.fill("#lp", ADMIN[1]); pg.click("#lf button[type=submit]")
    pg.wait_for_selector(".card")
    yield pg, server
    assert not errors, errors
    b.close(); p.stop()


def no_overflow(pg):
    return pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_views_fit_360_and_tap_targets(page):
    pg, _ = page
    for v in VIEWS:
        pg.click(f'[data-view="{v}"]'); pg.wait_for_timeout(150)
        assert pg.get_attribute(f'[data-view="{v}"]', "aria-pressed") == "true"
        assert pg.eval_on_selector("#results", "e => e.className") == f"grid v-{v}"
        assert no_overflow(pg), f"horizontal overflow in {v}"
        sizes = pg.eval_on_selector_all("[data-view]", "bs => bs.map(b => { const r = b.getBoundingClientRect(); return [r.width, r.height]; })")
        assert all(w >= 40 and h >= 40 for w, h in sizes), sizes
        if v == "compacta":
            h = pg.eval_on_selector(".v-compacta .cardlink", "e => e.getBoundingClientRect().height")
            assert h >= 40
    # each button has an accessible name and a tooltip
    for v in VIEWS:
        b = pg.locator(f'[data-view="{v}"]')
        assert b.get_attribute("aria-label") and b.get_attribute("title")


def test_view_remembered_per_device_over_server_default(page):
    pg, base = page
    pg.click('[data-view="compacta"]'); pg.wait_for_timeout(600)
    # server default changes from another device; this device keeps its own choice
    csrf = pg.evaluate("fetch('/api/auth/me').then(r => r.json()).then(m => m.csrf)")
    pg.request.put(f"{base}/api/preferencias/lista", headers={"X-CSRF-Token": csrf}, data={"vista": "una"})
    pg.reload(); pg.wait_for_selector(".card"); pg.wait_for_timeout(400)
    assert pg.eval_on_selector("#results", "e => e.className") == "grid v-compacta"
    # an old stored value migrates
    pg.evaluate("localStorage.setItem('vistaLista', JSON.stringify({vista: 'info', densidad: 4}))")
    pg.reload(); pg.wait_for_selector(".card"); pg.wait_for_timeout(400)
    assert pg.eval_on_selector("#results", "e => e.className") == "grid v-miniatura"


def test_keyboard_selects_view(page):
    pg, _ = page
    pg.focus('[data-view="una"]'); pg.keyboard.press("ArrowRight"); pg.keyboard.press("Enter")
    assert pg.get_attribute('[data-view="compacta"]', "aria-pressed") == "true"
    pg.keyboard.press("ArrowRight"); pg.keyboard.press(" ")
    assert pg.get_attribute('[data-view="miniatura"]', "aria-pressed") == "true"


def test_icon_thumbnail_option(page):
    pg, base = page
    pg.click('[data-view="miniatura"]')
    pg.evaluate("localStorage.setItem('miniaturas', 'icono')")
    pg.reload(); pg.wait_for_selector(".card")
    assert pg.locator("#results .thumb img").count() == 0
    assert pg.locator("#results .thumb .ph").count() > 0
