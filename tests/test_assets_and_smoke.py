"""v2.1.5: asset cache-busting, assets shipped in git, icon names, and a console-error / layout smoke test over every view."""
import datetime as dt
import io
import re
import subprocess
import tarfile
from pathlib import Path

import pytest
import requests

from app.assets_cache import IMMUTABLE, asset_versions, version_html
from tests.conftest import ADMIN
from tests.test_tokens_and_mcp import server  # noqa: F401  (live uvicorn fixture)

ROOT = Path(__file__).resolve().parents[1]
ASSET_RE = re.compile(r'/assets/([\w.\-/]+)\?v=([\w.\-]+)')


def _index(base):
    return requests.get(f"{base}/", timeout=10)


def test_index_versions_every_asset_and_headers(server):  # noqa: F811
    r = _index(server)
    assert r.headers["cache-control"] == "no-cache"
    refs = ASSET_RE.findall(r.text)
    assert {n for n, _ in refs} >= {"style.css", "icons.js", "i18n.js", "api.js", "app.js"}
    assert not re.search(r'["\']/assets/[\w.\-/]+["\']', r.text), "unversioned asset URL left in index.html"
    for name, v in refs:
        ok = requests.get(f"{server}/assets/{name}?v={v}", timeout=10)
        assert ok.status_code == 200 and ok.headers["cache-control"] == IMMUTABLE
        bare = requests.get(f"{server}/assets/{name}", timeout=10)
        assert bare.status_code == 200 and bare.headers["cache-control"] == "no-cache"
        assert "etag" in bare.headers and "last-modified" in bare.headers
        stale = requests.get(f"{server}/assets/{name}?v=2.1.3-deadbeef", timeout=10)
        assert stale.headers["cache-control"] == "no-cache"
        again = requests.get(f"{server}/assets/{name}", headers={"If-None-Match": bare.headers["etag"]}, timeout=10)
        assert again.status_code == 304


def test_versioned_urls_change_with_content(tmp_path):
    (tmp_path / "app.js").write_text("one")
    v1 = asset_versions(tmp_path)
    html = '<script src="/assets/app.js"></script><link href="/assets/missing.css">'
    out1 = version_html(html, v1)
    (tmp_path / "app.js").write_text("two")
    out2 = version_html(html, asset_versions(tmp_path))
    assert "?v=" in out1 and out1 != out2 and '/assets/missing.css"' in out1


def test_index_assets_exist_in_git_archive_of_head(tmp_path):
    """Catches gitignored/untracked assets: what the mini PC clones must contain every referenced file."""
    try:
        blob = subprocess.run(["git", "archive", "--format=tar", "HEAD", "static"], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:  # pragma: no cover
        pytest.skip(f"git not available: {e}")
    tarfile.open(fileobj=io.BytesIO(blob)).extractall(tmp_path, filter="data")
    html = (tmp_path / "static" / "index.html").read_text(encoding="utf-8")
    names = set(re.findall(r'["\']/assets/([\w.\-/]+)', html))
    assert names
    for n in names:
        assert (tmp_path / "static" / "assets" / n).is_file(), f"{n} missing from git HEAD"
    # every working-tree asset is tracked too (so the next commit can't silently drop one)
    for p in (ROOT / "static" / "assets").iterdir():
        assert (tmp_path / "static" / "assets" / p.name).is_file(), f"{p.name} is untracked/ignored"


def _icon_names():
    src = (ROOT / "static/assets/icons.js").read_text(encoding="utf-8")
    body = src[src.index("const ICONS"):]
    return set(re.findall(r'^\s*"([\w-]+)":\s*[`"]', body, re.M)) | set(re.findall(r'^\s*([a-z]\w*):\s*[`"]', body, re.M))


def test_every_icon_name_used_exists():
    names = _icon_names()
    app = (ROOT / "static/assets/app.js").read_text(encoding="utf-8") + (ROOT / "static/index.html").read_text(encoding="utf-8")
    used = set(re.findall(r'\bic\(\s*["\']([\w-]+)["\']', app))
    for m in re.finditer(r'const (SECTIONS|SRC_ICON|ICON|TAG_ICON)\s*=\s*([^;]+);', app):
        body = m.group(2)
        if m.group(1) == "TAG_ICON":
            used |= set(re.findall(r'\[\s*"[^"]+"\s*,\s*"([\w-]+)"', body))
        elif m.group(1) == "SECTIONS":
            used |= set(re.findall(r'\["\w+",\s*"([\w-]+)"', body))
        elif m.group(1) == "SRC_ICON":
            used |= set(re.findall(r':\s*"([\w-]+)"', body))
        else:
            used |= set(re.findall(r'\[\s*"([\w-]+)"', body))
    used |= {"circle-dashed", "utensils-crossed", "sun", "moon", "link"}
    assert len(used) > 40
    assert not sorted(used - names), sorted(used - names)


# ---------------------------------------------------------------- browser smoke over messy data
pw = pytest.importorskip("playwright.sync_api")

LAYOUT_JS = """() => {
  const vw = innerWidth, out = {overflow: document.documentElement.scrollWidth - vw, problems: []};
  const ov = (a, b) => !(a.left >= b.right - 1 || a.right <= b.left + 1 || a.top >= b.bottom - 1 || a.bottom <= b.top + 1);
  const h1 = document.querySelector('main .hero h1'), act = document.querySelector('main .hero > .hero-actions, main .hero > .row');
  if (h1 && act && ov(h1.getBoundingClientRect(), act.getBoundingClientRect())) out.problems.push('hero title overlaps actions');
  const days = [...document.querySelectorAll('.day')].map(d => d.getBoundingClientRect());
  if (location.hash.startsWith('#/planificador')) {
    if (days.length !== 7) out.problems.push('days=' + days.length);
    days.forEach((d, i) => { if (d.width < 120 || d.height < 40) out.problems.push('tiny day ' + i);
      if (d.right > vw + 1 || d.left < -1) out.problems.push('day off-screen ' + i);
      days.slice(i + 1).forEach((e, j) => { if (ov(d, e)) out.problems.push(`days ${i}/${i + j + 1} overlap`); }); });
  }
  return out; }"""


@pytest.fixture()
def messy(server, services):  # noqa: F811
    """Real third-party seed (already loaded) plus edge cases and a full week that references a deleted recipe."""
    services.auth.create_admin(*ADMIN)
    R = services.recipes
    edge = [R.create({"titulo": "Receta con un título larguísimo " * 6}),
            R.create({"titulo": "Cien raciones", "raciones": 100}),
            R.create({"titulo": "Sin nada", "raciones": 1, "etiquetas": [], "pasos": [], "ingredientes": []}),
            R.create({"titulo": "Supercalifragilisticoespialidosoconpatatasyunpocodesal", "raciones": 3})]
    ids = [r["id"] for r in edge] + [row[0] for row in services.db.conn.execute("SELECT id FROM recipes ORDER BY id LIMIT 20")]
    mon = dt.date.today() - dt.timedelta(days=dt.date.today().weekday())
    k = 0
    for d in range(7):
        for c in ("comida", "cena"):
            services.planner.add(str(mon + dt.timedelta(days=d)), c, ids[k % len(ids)], None, "nota larga " * 8 if k % 3 == 0 else "")
            k += 1
    R.delete(edge[0]["id"])
    return server


@pytest.mark.parametrize("vw", [(360, 800), (390, 844), (1440, 900)], ids=["360", "390", "desktop"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_no_console_errors_and_sane_layout_everywhere(messy, vw, theme):
    base = messy
    try:
        p = pw.sync_playwright().start(); b = p.chromium.launch()
    except Exception as e:  # pragma: no cover
        pytest.skip(f"chromium not available: {e}")
    try:
        ctx = b.new_context(viewport={"width": vw[0], "height": vw[1]}, locale="es-ES", color_scheme=theme, has_touch=vw[0] < 700)
        ctx.add_init_script(f"localStorage.setItem('tema','{theme}')")
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(f"js: {e}"))
        pg.on("console", lambda m: m.type == "error" and "cdninstagram" not in m.text and "instagram.com" not in (m.location or {}).get("url", "") and errs.append(f"console: {m.text}"))
        # third-party embeds (Instagram) are cancelled on navigation; only our own origin must not fail
        pg.on("requestfailed", lambda r: r.url.startswith(base) and errs.append(f"failed: {r.url}"))
        pg.on("response", lambda r: r.status >= 400 and "/api/auth/me" not in r.url and errs.append(f"{r.status}: {r.url}"))
        pg.goto(f"{base}/#/recetas"); pg.wait_for_selector("#lf")
        pg.fill("#lu", ADMIN[0]); pg.fill("#lp", ADMIN[1]); pg.click("#lf button[type=submit]"); pg.wait_for_selector(".card")
        bad = {}
        def check(tag):
            r = pg.evaluate(LAYOUT_JS)
            if r["overflow"] > 0 or r["problems"]:
                bad[tag] = r
        for dens in ("comoda", "compacta"):
            pg.evaluate(f"localStorage.setItem('interfaz','{dens}')"); pg.goto(f"{base}/#/recetas"); pg.reload(); pg.wait_for_selector(".card")
            for v in ("una", "compacta", "miniatura", "cuadricula"):
                pg.click(f'[data-view="{v}"]'); pg.wait_for_timeout(150); check(f"{dens}/recetas/{v}")
            for route in ("receta/2", "planificador", "compra", "ajustes"):
                pg.goto(f"{base}/#/{route}"); pg.wait_for_timeout(700); check(f"{dens}/{route}")
            # an empty week, three weeks ahead
            pg.goto(f"{base}/#/planificador"); pg.wait_for_selector("#wNext")
            for _ in range(3):
                pg.click("#wNext"); pg.wait_for_timeout(250)
            check(f"{dens}/planificador-vacio")
        assert not bad, bad
        assert not errs, errs
    finally:
        b.close(); p.stop()
