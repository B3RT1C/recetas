import re
from pathlib import Path

ICONS = Path(__file__).resolve().parents[1] / "static" / "assets" / "icons.js"


def test_icon_bodies_have_no_svg_wrapper():
    # ic() wraps each body in its own <svg>; a nested unclosed <svg> swallows following text.
    bodies = re.findall(r'^\s*"[\w-]+": "(.*)",?$', ICONS.read_text(encoding="utf-8"), re.M)
    assert len(bodies) > 50
    assert not [b for b in bodies if "<svg" in b or "</svg" in b]
