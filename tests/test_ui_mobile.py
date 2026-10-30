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
        assert all(w >= 44 and h >= 44 for w, h in sizes), sizes
        if v == "compacta":
            h = pg.eval_on_selector(".v-compacta .cardlink", "e => e.getBoundingClientRect().height")
            assert h >= 44
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


CONTRAST_JS = """([a, b]) => {
  const rgb = s => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = c => { const [r, g, b] = rgb(c).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; });
                     return .2126 * r + .7152 * g + .0722 * b; };
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05);
}"""


def test_header_buttons_fit_360(page):
    pg, _ = page
    sel = ".hero-actions .btn:not([hidden]), .fab, #filtBtn"
    boxes = pg.eval_on_selector_all(sel, "bs => bs.filter(b => b.getClientRects().length).map(b => { const r = b.getBoundingClientRect(); return [r.left, r.right, r.width, r.height, b.getAttribute('aria-label') || b.textContent.trim()]; })")
    assert len(boxes) >= 3 and all(l >= 0 and r <= 360 and w >= 44 and h >= 44 and name for l, r, w, h, name in boxes), boxes
    assert no_overflow(pg)
    # Seleccionar / Exportar live in the overflow menu
    pg.click("#moreBtn"); assert pg.is_visible("#selBtn") and pg.is_visible("#expBtn")
    hs = pg.eval_on_selector_all("#moreMenu .mi", "bs => bs.filter(b => b.getClientRects().length).map(b => b.getBoundingClientRect().height)")
    assert hs and min(hs) >= 44
    pg.keyboard.press("Escape"); assert pg.is_hidden("#moreMenu")


def test_all_tap_targets_44(page):
    pg, _ = page
    small = pg.evaluate("""[...document.querySelectorAll('main button, main a.btn, main .input, .fab, .tabbar a')]
      .filter(e => e.getClientRects().length && !e.closest('[hidden]') && !e.closest('.card'))
      .map(e => { const r = e.getBoundingClientRect(); return [e.id || e.textContent.trim().slice(0, 20), Math.round(r.width), Math.round(r.height)]; })
      .filter(([, w, h]) => w < 44 || h < 44)""")
    assert not small, small


def test_filters_popover_holds_chips_and_favourites(page):
    pg, _ = page
    assert pg.is_hidden("#favF") and pg.is_hidden("[data-tag]")
    pg.click("#filtBtn"); pg.click("#favF"); pg.locator("[data-tag]").first.click(); pg.wait_for_timeout(200)
    assert pg.text_content("#filtN") == "2"
    assert no_overflow(pg)


def test_density_toggle(page):
    pg, _ = page
    pad = lambda: pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--section').trim()")
    assert pg.evaluate("document.documentElement.dataset.density") == "comoda"
    comfy = pad()
    pg.goto(pg.url.split("#")[0] + "#/ajustes"); pg.wait_for_selector("input[name=interfaz]")
    pg.check("input[name=interfaz][value=compacta]"); pg.wait_for_timeout(300)
    assert pg.evaluate("document.documentElement.dataset.density") == "compacta"
    assert pg.evaluate("localStorage.getItem('interfaz')") == "compacta" and pad() != comfy
    pg.reload(); pg.wait_for_timeout(300)
    assert pg.evaluate("document.documentElement.dataset.density") == "compacta"
    assert pg.evaluate("fetch('/api/preferencias/lista').then(r => r.json()).then(p => p.interfaz)") == "compacta"


def test_grid_columns_match_slider_and_titles_wrap(page):
    pg, _ = page
    pg.click('[data-view="cuadricula"]'); pg.wait_for_timeout(200)
    assert pg.get_attribute("#densR", "max") == "3"
    # no extra row: the switcher shares the row with the count and the first card follows right after
    cnt, sw = (pg.eval_on_selector(s, "e => e.getBoundingClientRect().top") for s in ("#count", ".vseg"))
    assert abs(cnt - sw) < 30
    assert pg.eval_on_selector(".listbar", "e => e.getBoundingClientRect().height") < 60
    assert pg.locator("main > .listbar .dens, main > .listbar #densR").count() == 0
    # the columns slider lives in the ⋯ panel
    pg.click("#moreBtn"); assert pg.is_visible("#densR")
    for n in ("2", "3"):
        if pg.input_value("#densR") != n:
            pg.fill("#densR", n); pg.dispatch_event("#densR", "input"); pg.wait_for_timeout(200)
        shown = pg.eval_on_selector("#results", "e => getComputedStyle(e).gridTemplateColumns.split(' ').length")
        assert str(shown) == n == pg.text_content("#densO")
    assert pg.evaluate("localStorage.getItem('densidadMovil')") == "3"
    h3 = pg.eval_on_selector(".v-cuadricula .card h3", "e => [getComputedStyle(e).webkitLineClamp, getComputedStyle(e).whiteSpace]")
    assert h3 == ["2", "normal"]


def test_grid_defaults_to_two_columns_on_mobile(page):
    pg, _ = page
    pg.click('[data-view="cuadricula"]'); pg.wait_for_timeout(200)
    assert pg.text_content("#densO") == "2"
    # the meta line (time + price) is never clipped
    clipped = pg.eval_on_selector_all(".v-cuadricula .gmeta", """ps => ps.filter(p => {
      const r = p.getBoundingClientRect();
      return p.scrollWidth > p.clientWidth + 1 || [...p.querySelectorAll('.gm')].some(g => { const b = g.getBoundingClientRect(); return b.right > r.right + 1 || b.bottom > r.bottom + 1; });
    }).length""")
    assert clipped == 0
    assert pg.locator(".v-cuadricula .gmeta .gm").filter(has_text="€").count() > 0
    assert pg.eval_on_selector("#results", "e => getComputedStyle(e).gridTemplateColumns.split(' ').length") == 2


def test_favourite_star_same_colour_in_both_lists(page):
    pg, base = page
    csrf = pg.evaluate("fetch('/api/auth/me').then(r => r.json()).then(m => m.csrf)")
    rid = pg.request.get(f"{base}/api/recipes?limit=1").json()
    rid = (rid.get("items", rid) if isinstance(rid, dict) else rid)[0]["id"]
    pg.request.patch(f"{base}/api/recipes/{rid}", headers={"X-CSRF-Token": csrf}, data={"favorito": True})
    pg.reload(); pg.wait_for_selector(".card")
    colours = []
    for v in ("compacta", "miniatura"):
        pg.click(f'[data-view="{v}"]'); pg.wait_for_timeout(200)
        el = pg.locator(".card h3 .ic").first
        if el.count() == 0:
            pytest.skip("no favourite in the fixture data")
        colours.append(el.evaluate("e => getComputedStyle(e).color"))
    accent = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
    assert colours[0] == colours[1], colours
    assert accent


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_active_view_button_contrast(page, theme):
    pg, _ = page
    pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
    pg.click('[data-view="una"]'); pg.wait_for_timeout(200)
    on, track = pg.eval_on_selector('[data-view="una"]', "e => [getComputedStyle(e).backgroundColor, getComputedStyle(e.parentElement).backgroundColor]")
    assert pg.evaluate(CONTRAST_JS, [on, track]) >= 3, (on, track)
    off = pg.eval_on_selector('[data-view="una"]', "e => getComputedStyle(e).color")
    assert pg.evaluate(CONTRAST_JS, [off, on]) >= 3


def test_subtitle_single_line_and_no_repeat(page):
    pg, _ = page
    sub = pg.locator(".hero .sub")
    if sub.count():
        assert "recetas" not in sub.text_content() and "completas" not in sub.text_content()
        assert sub.evaluate("e => e.getClientRects().length === 1 && e.getBoundingClientRect().height < 30")
    h = pg.eval_on_selector(".hero", "e => e.getBoundingClientRect().height")
    assert h < 90


def test_fab_does_not_cover_last_card(page):
    pg, _ = page
    for v in ("una", "cuadricula"):
        pg.click(f'[data-view="{v}"]'); pg.wait_for_timeout(200)
        pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(100)
        pg.mouse.wheel(0, -40); pg.wait_for_timeout(400)  # scrolling up shows the FAB again
        fab = pg.eval_on_selector(".fab", "e => [e.getBoundingClientRect().top, getComputedStyle(e).opacity]")
        assert fab[1] == "1"
        last = pg.eval_on_selector_all("#results .card", "cs => cs.at(-1).getBoundingClientRect().bottom")
        assert last <= fab[0], (v, last, fab)
    pg.evaluate("window.scrollTo(0, 0)"); pg.wait_for_timeout(100)
    pg.mouse.wheel(0, 400); pg.wait_for_timeout(400)
    assert "fab-hide" in pg.get_attribute(".fab", "class")


def test_fab_respects_reduced_motion(page):
    pg, _ = page
    pg.emulate_media(reduced_motion="reduce")
    assert pg.eval_on_selector(".fab", "e => getComputedStyle(e).transitionDuration") in ("0s", "0s, 0s")


_CONTRAST_JS = """([sels]) => {
  const rgb = c => { const m = c.match(/[\\d.]+/g).map(Number); return m.slice(0, 3); };
  const lum = c => { const v = rgb(c).map(x => { x /= 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; });
                     return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };
  const okl = c => { const v = rgb(c).map(x => { x /= 255; return x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; });
    const l = Math.cbrt(.4122214708*v[0]+.5363325363*v[1]+.0514459929*v[2]), m = Math.cbrt(.2119034982*v[0]+.6806995451*v[1]+.1073969566*v[2]),
          s = Math.cbrt(.0883024619*v[0]+.2817188376*v[1]+.6299787005*v[2]);
    return .2104542553*l + .7936177850*m - .0040720468*s; };
  const st = getComputedStyle(document.documentElement), get = n => {
    const d = document.createElement('i'); d.style.color = `var(${n})`; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; };
  const out = {};
  for (const n of ['--elev-0', '--elev-1', '--elev-2', '--elev-3', '--text', '--muted', '--accent']) out[n] = get(n);
  out.ratio = ratio; out.okl = okl;
  return { c: Object.fromEntries(Object.entries(out).filter(([k]) => k.startsWith('--'))),
           L: ['--elev-0','--elev-1','--elev-2','--elev-3'].map(n => okl(out[n])),
           text: ['--elev-1','--elev-2','--elev-3'].map(s => [ratio(out['--text'], out[s]), ratio(out['--muted'], out[s])]),
           acc: ['--elev-1','--elev-2'].map(s => ratio(out['--accent'], s === '--elev-1' ? out['--elev-1'] : out['--elev-2'])),
           card: ratio(out['--elev-1'], out['--elev-0']),
           cardBorder: getComputedStyle(document.querySelector('#results .card')).borderTopWidth,
           cardShadow: getComputedStyle(document.querySelector('#results .card')).boxShadow };
}"""


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_surface_elevation_and_text_contrast(page, theme):
    pg, _ = page
    pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'"); pg.wait_for_timeout(100)
    r = pg.evaluate(_CONTRAST_JS, [None])
    L = r["L"]
    print(theme, "OKLCH L", [round(x * 100, 1) for x in L], "card/bg ratio", round(r["card"], 3))
    assert r["cardBorder"] == "1px"
    if theme == "dark":
        # each elevation step is at least 6 points lighter (OKLCH L, 0–100)
        assert all(b - a >= 0.06 for a, b in zip(L, L[1:])), L
        assert r["card"] >= 1.15
    else:
        assert L[1] - L[0] >= 0.02 and r["cardShadow"] != "none"
    for txt, muted in r["text"]:
        assert txt >= 4.5 and muted >= 4.5, r["text"]
    assert all(a >= 3 for a in r["acc"]), r["acc"]
