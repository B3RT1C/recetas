"""UI uses inline Lucide line icons (static/assets/icons.js); no emoji may sneak back into static/."""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"
# pictographs, dingbats, misc symbols/arrows, variation selector, ZWJ, fullwidth plus
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2190-\u21FF\u2300-\u23FF\uFE0F\u200D\uFF0B]")


def test_no_emoji_in_static():
    hits = []
    for f in STATIC.rglob("*"):
        if f.is_file() and f.suffix in {".js", ".html", ".css", ".json", ".svg", ".webmanifest"}:
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if EMOJI.search(line):
                    hits.append(f"{f.relative_to(STATIC)}:{n}: {line.strip()[:80]}")
    assert not hits, "Emoji found (use ic(name) from icons.js):\n" + "\n".join(hits)


def test_icons_vendored_with_license_and_current_color():
    js = (STATIC / "assets" / "icons.js").read_text(encoding="utf-8")
    assert 'stroke="currentColor"' in js and "ISC" in js
    assert "ISC License" in (STATIC / "assets" / "LICENSE-lucide.txt").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "/assets/icons.js" in html and "cdn" not in html.lower() and "https://" not in html
    # every icon name used by the app exists in the vendored map
    app = (STATIC / "assets" / "app.js").read_text(encoding="utf-8")
    known = set(re.findall(r'^\s*"([a-z0-9-]+)":', js, re.M))
    missing = {n for n in re.findall(r'\bic\("([a-z0-9-]+)"', app)} - known
    assert not missing, missing
