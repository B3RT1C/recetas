"""Sample/demo data ships only free covers (data/sample/covers) with attribution; no Instagram media."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERS = ROOT / "data" / "sample" / "covers"


def test_every_sample_recipe_has_attributed_cover():
    recetas = json.loads((ROOT / "data" / "sample" / "recetas-demo.json").read_text(encoding="utf-8"))["recetas"]
    attribution = (COVERS / "ATTRIBUTION.md").read_text(encoding="utf-8")
    for r in recetas:
        name = Path(r["foto"]).name
        assert (COVERS / name).is_file(), name
        line = next(l for l in attribution.splitlines() if l.startswith(f"| {name} "))
        assert "commons.wikimedia.org" in line and ("CC0" in line or "ublic domain" in line)
        assert not r.get("video_url")


def test_static_build_ships_only_sample_covers(tmp_path):
    out = tmp_path / "dist"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_static.py"), "--out", str(out)],
                   check=True, cwd=ROOT, capture_output=True)
    assert not list(out.rglob("*.mp4"))
    data = json.loads((out / "data" / "recipes.json").read_text(encoding="utf-8"))
    for r in data["recetas"]:
        assert r["portada"] and r["portada"].startswith("media/covers/")
        assert (out / r["portada"]).is_file()
        assert r["media"]["video"] is None and "instagram" not in (r.get("source_url") or "")
