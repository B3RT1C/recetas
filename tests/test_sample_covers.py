import json
from pathlib import Path

from app.services import covers

ROOT = Path(__file__).resolve().parent.parent


def test_every_sample_recipe_has_its_own_credited_cc0_photo():
    data = json.loads((ROOT / "data/sample/recetas-demo.json").read_text(encoding="utf-8"))
    recipes = data.get("recetas", data) if isinstance(data, dict) else data
    stems = [Path(r["foto"]).stem for r in recipes]
    assert len(stems) == len(set(stems)), "duplicate sample photo"
    lib = {x["id"]: x for x in covers.library()}
    for s in stems:
        assert s in lib, f"{s} missing from ATTRIBUTION.md"
        assert (ROOT / "data/sample/covers" / f"{s}.jpg").exists()
        assert lib[s]["licencia"] and lib[s]["autor"] and lib[s]["fuente_url"].startswith("https://commons.wikimedia.org")
