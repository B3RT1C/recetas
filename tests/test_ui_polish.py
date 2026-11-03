"""v2.1.6 UI polish: CSS without conflicting duplicate definitions, settings sub-routes, dialogs closed on navigation, localised dates."""
import re
from pathlib import Path

import pytest

from tests.conftest import ADMIN
from tests.test_tokens_and_mcp import server  # noqa: F401  (live uvicorn fixture)

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static/assets/style.css").read_text(encoding="utf-8")
STRUCTURAL = {"display", "grid-template-columns", "position", "flex-direction"}


def _rules(src):
    """(media context, selector, body) for every style rule, comments stripped."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    ctx, last, out = [], 0, []
    for m in re.finditer(r"[{}]", src):
        if m.group() == "{":
            ctx.append(src[last:m.start()].strip())
        else:
            head = ctx.pop()
            if not head.startswith("@"):
                out.append((tuple(ctx), head, src[last:m.start()].strip()))
        last = m.end()
    return out


def test_no_conflicting_structural_duplicates():
    """The same selector must not be laid out two different ways (e.g. one class name reused by two components)."""
    seen, bad = {}, []
    for ctx, sel, body in _rules(CSS):
        for s in (" ".join(x.split()) for x in sel.split(",")):
            for decl in body.split(";"):
                if ":" not in decl:
                    continue
                k, v = (p.strip() for p in decl.split(":", 1))
                if k not in STRUCTURAL:
                    continue
                key = (ctx, s, k)
                if key in seen and seen[key] != v:
                    bad.append((ctx, s, k, seen[key], v))
                seen[key] = v
    assert not bad, bad


@pytest.mark.parametrize("cls", [".form-grid", ".wizard-steps", ".dfacts", ".settings"])
def test_component_classes_defined_once_at_top_level(cls):
    tops = [b for ctx, sel, b in _rules(CSS) if not ctx and sel == cls]
    assert len(tops) == 1, (cls, tops)


def test_detail_and_list_facts_do_not_share_a_class():
    js = (ROOT / "static/assets/app.js").read_text(encoding="utf-8")
    body = js[js.index("async function viewDetail"):js.index("function", js.index("async function viewDetail") + 30)]
    assert 'class="facts' not in body


SUBS = ("apariencia", "portadas", "ia", "agentes", "importacion", "precios", "copias", "cuenta", "estado")


@pytest.fixture()
def browser_page(server, services):  # noqa: F811
    pw = pytest.importorskip("playwright.sync_api")
    services.auth.create_admin(*ADMIN)
    try:
        p = pw.sync_playwright().start(); b = p.chromium.launch()
    except Exception as e:  # pragma: no cover
        pytest.skip(f"chromium not available: {e}")
    pages, errors = [], []

    def make(width, lang="es"):
        ctx = b.new_context(viewport={"width": width, "height": 844}, locale="es-ES", has_touch=width < 700)
        ctx.add_init_script(f"localStorage.setItem('lang','{lang}')")
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"{server}/#/recetas"); pg.wait_for_selector("#lf")
        pg.fill("#lu", ADMIN[0]); pg.fill("#lp", ADMIN[1]); pg.click("#lf button[type=submit]"); pg.wait_for_selector(".card")
        pages.append(pg)
        return pg
    yield make, server
    assert not errors, errors
    b.close(); p.stop()


def test_settings_index_on_mobile_and_subscreens(browser_page):
    make, base = browser_page
    pg = make(390)
    pg.goto(f"{base}/#/ajustes"); pg.wait_for_selector(".side a")
    links = pg.eval_on_selector_all(".side a", "as => as.map(a => a.getAttribute('href'))")
    assert links == [f"#/ajustes/{s}" for s in SUBS]
    assert not pg.is_visible(".s-content")
    assert pg.eval_on_selector_all(".side a", "as => Math.min(...as.map(a => a.getBoundingClientRect().height))") >= 44
    assert pg.locator(".tabs, .side[style*=overflow]").count() == 0
    for s, sel in [("apariencia", "input[name=interfaz]"), ("ia", "#aiF"), ("cuenta", "#logout"), ("copias", "#stExp"), ("precios", "#s-precios")]:
        pg.goto(f"{base}/#/ajustes/{s}"); pg.wait_for_selector(sel)
        assert not pg.is_visible(".s-menu")
        assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), s
    # every existing appearance setting still works
    pg.goto(f"{base}/#/ajustes/apariencia"); pg.wait_for_selector("input[name=tema]")
    pg.check("input[name=tema][value=dark]")
    assert pg.evaluate("document.documentElement.dataset.theme") == "dark"
    assert pg.evaluate("localStorage.getItem('tema')") == "dark"
    pg.check("input[name=interfaz][value=compacta]"); pg.wait_for_timeout(300)
    assert pg.evaluate("localStorage.getItem('interfaz')") == "compacta"
    # the shopping list is never sent to any store
    pg.goto(f"{base}/#/ajustes/precios"); pg.wait_for_selector("#s-precios")
    assert "ninguna tienda" in pg.inner_text("#s-precios")


def test_settings_desktop_two_columns(browser_page):
    make, base = browser_page
    pg = make(1280)
    pg.goto(f"{base}/#/ajustes"); pg.wait_for_selector("#s-ap")
    menu, content = (pg.locator(s).bounding_box() for s in (".s-menu", ".s-content"))
    assert menu["x"] + menu["width"] <= content["x"]
    assert pg.get_attribute(".side a[aria-current=page]", "href") == "#/ajustes/apariencia"
    pg.click(".side a[href='#/ajustes/ia']"); pg.wait_for_selector("#aiF")
    assert pg.get_attribute(".side a[aria-current=page]", "href") == "#/ajustes/ia"
    # the API key field never echoes a stored key
    assert pg.evaluate("[...document.querySelectorAll('#aiF input')].every(i => i.type !== 'text' || !/^sk-/.test(i.value))")


@pytest.mark.parametrize("width", [390, 1280])
def test_dialogs_close_on_navigation(browser_page, width):
    make, base = browser_page
    pg = make(width)
    pg.goto(f"{base}/#/receta/2"); pg.wait_for_selector(".d-head")
    pg.evaluate("dialog('<p>x</p>')"); pg.wait_for_selector("#dlg[open]")
    pg.evaluate("location.hash = '#/planificador'"); pg.wait_for_selector(".day")
    assert pg.evaluate("document.querySelectorAll('dialog[open]').length") == 0
    pg.evaluate("history.back()"); pg.wait_for_selector(".d-head")
    assert pg.evaluate("document.querySelectorAll('dialog[open]').length") == 0


def test_dates_follow_language(browser_page):
    make, base = browser_page
    es, en = make(1280, "es"), make(1280, "en")
    f = "fmtDay('2026-11-03', 'mid')"
    assert es.evaluate(f) != en.evaluate(f)
    assert "nov" in es.evaluate(f).lower() and "Nov" in en.evaluate(f)
    assert "Tue" in en.evaluate(f)
