import pytest

from app.services import units as U


def test_canonical_volume_to_grams_with_density():
    q, u = U.canonical(1, "taza", "Harina de trigo")
    assert u == "g" and q == pytest.approx(127.2)


def test_liquids_stay_ml_and_mass_scales():
    assert U.canonical(2, "cda", "aceite de oliva") == (30, "ml")
    assert U.canonical(1.5, "kg", "carne picada") == (1500, "g")
    assert U.canonical(3, "dientes", "ajo") == (3, "diente")


def test_convert():
    assert U.convert(1, "taza", "g", "azúcar") == pytest.approx(204)
    assert U.convert(1000, "ml", "l") == 1
    assert U.convert(1, "ud", "g", "huevo") is None
    assert U.convert(1, "taza", "g", "pollo") is None


@pytest.mark.parametrize("raw,norm", [("Tomates maduros", "tomate"), ("limones", "limon"),
                                      ("Cebolla picada", "cebolla"), ("Ajo (laminado)", "ajo")])
def test_norm_name(raw, norm):
    assert U.norm_name(raw) == norm


def test_rounding_eggs_and_grams():
    assert U.round_qty(1.5, "ud", "huevos")[0] == 2
    assert U.round_qty(0.3, "ud", "huevo")[0] == 1
    assert U.round_qty(1.4, "dientes", "ajo")[0] == 1.5
    assert U.round_qty(333.3, "g", "harina")[0] == 330
    assert U.round_qty(0.66, "cda", "sal")[0] == 0.75


def test_display_and_scale():
    assert U.display(1340, "g") == "1,34 kg"
    assert U.display(0.5, "cda") == "½ cda"
    r = U.scale_recipe({"raciones": 4, "ingredientes": [
        {"nombre": "huevos", "cantidad_num": 3, "unidad": "ud"},
        {"nombre": "sal", "cantidad_num": None, "cantidad_normal": "al gusto", "unidad": ""}]}, 2)
    assert r["ingredientes"][0]["cantidad"] == 2 and r["ingredientes"][0]["redondeado"]
    assert r["ingredientes"][1]["texto"] == "al gusto"
