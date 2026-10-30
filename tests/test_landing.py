import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mod():
    spec = importlib.util.spec_from_file_location("check_landing", ROOT / "scripts/check_landing.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_landing_has_no_unexpected_external_urls_and_local_refs_exist():
    assert _mod().check() == []


def test_landing_bilingual_with_hreflang_and_meta():
    for p, lang in (("landing/index.html", 'lang="es-ES"'), ("landing/en/index.html", 'lang="en"')):
        t = (ROOT / p).read_text()
        assert lang in t and 'hreflang="es"' in t and 'hreflang="en"' in t
        for needle in ('name="description"', 'property="og:image"', 'name="twitter:card"', 'rel="icon"', 'id="themeBtn"'):
            assert needle in t
    assert (ROOT / "landing/_headers").exists() and (ROOT / "landing/README.md").exists()


def test_repo_link_hidden_while_private():
    import json
    cfg = json.loads((ROOT / "landing/site.config.json").read_text())
    t = (ROOT / "landing/index.html").read_text()
    assert (cfg["repo_url"] in t) == bool(cfg["repo_public"])


def test_live_demo_and_carousel_strict_csp_and_sample_data_only():
    import json, re
    for p, q in (("landing/index.html", ""), ("landing/en/index.html", "?lang=en")):
        t = (ROOT / p).read_text()
        assert t.count(f'src="/demo/{q}#/recetas"') == 2 and 'data-tour="desk"' in t and 'data-tour="phone"' in t
        assert 'id="cartrack"' in t and 'id="carprev"' in t and 'id="carnext"' in t and 'id="carplay"' in t
        lang = "en" if q else "es"
        assert 'class="car car-d"' in t and 'class="car car-m"' in t and 'id="cartrackm"' in t
        mob = t[t.index('class="car car-m"'):]
        mob = mob[:mob.index("</ul>")]
        assert mob.count('class="car-s') == 9 and mob.count('car-s car-wide') == 1
        assert set(re.findall(r"/img/(g-[a-z-]+?)-(?:light|dark)", mob)) == {"g-cuadricula"}, "exactly one desktop shot on mobile"
        for n in ("lista", "detalle", "ingredientes", "cocina", "planificador", "compra", "importar", "ajustes"):
            for th in ("light", "dark"):
                assert f"/img/mc-{n}-{lang}-{th}.webp" in mob and (ROOT / f"landing/img/mc-{n}-{lang}-{th}.webp").exists()
        assert 'aria-roledescription=' in t and 'id="lb"' in t and 'id="cr"' in t and 'loading="lazy"' in t
        assert not re.search(r"<script(?![^>]*\bsrc=)", t), "inline script"
        assert " style=" not in t and "<style" not in t, "inline style"
        assert 'src="/assets/landing.3.js" defer' in t
    js = (ROOT / "landing/assets/landing.3.js").read_text()
    assert "fetch(" not in js and "XMLHttpRequest" not in js
    data = (ROOT / "landing/assets/demo-data.js").read_text()
    assert data.count('"s":') == 12
    for s in re.findall(r'"s":"([a-z-]+)"', data):
        assert (ROOT / f"landing/img/r/{s}.webp").exists()
    # the embedded app is the real static/ UI over a recorded, sanitized read-only API
    demo = ROOT / "landing/demo"
    idx = (demo / "index.html").read_text()
    assert 'name="robots" content="noindex' in idx and idx.index("mock-api.js") < idx.index("assets/api.js")
    assert not re.search(r"<script(?![^>]*\bsrc=)", idx)
    for f in (ROOT / "static/assets").iterdir():
        assert (demo / "assets" / f.name).read_bytes() == f.read_bytes()
    for f in (ROOT / "scripts/landing_demo").iterdir():
        assert (demo / f.name).read_bytes() == f.read_bytes(), f"stale demo/{f.name}: run build_landing_demo.py"
    api = json.loads((demo / "data/api.json").read_text())
    raw = json.dumps(api)
    assert api["get"]["/api/auth/me"]["usuario"] == "demo"
    assert "instagram.com" not in raw and "/tmp/" not in raw and not re.search(r"sk-[A-Za-z0-9]{8}", raw)
    assert all(not r.get("video_url") for r in api["get"]["/api/recipes"])
    h = (ROOT / "landing/_headers").read_text()
    assert "/demo/*" in h and "frame-ancestors 'self'" in h and "frame-src 'self'" in h
