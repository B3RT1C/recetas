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
