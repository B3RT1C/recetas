from app.services.caption_parser import parse_caption, parse_ingredient

CAPTION = """🍝 PASTA CREMOSA DE POLLO en 20 minutos!
Para 4 personas

Ingredientes:
- 400 g de pasta
- 2 pechugas de pollo
- ½ cebolla
- 200 ml de nata
- 2 dientes de ajo
- Sal y pimienta al gusto

Preparación:
1. Cuece la pasta 10 minutos.
2. Dora el pollo con el ajo 8 min.
3. Añade la nata y mezcla.
#pasta #recetasfaciles @alguien"""


def test_full_caption():
    d = parse_caption(CAPTION, autor="@x", video_url="https://www.instagram.com/reel/ABC123/")
    assert d["titulo"] == "Pasta cremosa de pollo en 20 minutos"
    assert d["raciones"] == 4 and d["raciones_estimadas"] is False
    names = [i["nombre"] for i in d["ingredientes"]]
    assert names == ["pasta", "pechugas de pollo", "cebolla", "nata", "ajo", "sal y pimienta al gusto"]
    assert d["ingredientes"][2]["cantidad_num"] == 0.5
    assert d["ingredientes"][-1]["estimada"] is True
    assert [s["minutos"] for s in d["pasos"]] == [10, 8, None]
    assert not any("#" in s["texto"] for s in d["pasos"])
    assert "pasta" in d["etiquetas"] and "pollo" in d["etiquetas"]


def test_units_and_word_numbers():
    assert parse_ingredient("1 kg de patatas") == {"nombre": "patatas", "cantidad_num": 1000, "unidad": "g", "estimada": False, "precio_eur": None}
    assert parse_ingredient("dos huevos")["cantidad_num"] == 2
    i = parse_ingredient("2 cucharadas de aceite de oliva")
    assert (i["cantidad_num"], i["unidad"], i["nombre"]) == (2, "cda", "aceite de oliva")
    assert parse_ingredient("1 1/2 tazas de leche")["cantidad_num"] == 1.5
    assert parse_ingredient("Harina 200 g")["cantidad_num"] == 200


def test_inline_ingredients_and_steps_header_variants():
    d = parse_caption("Flan casero\nIngredientes: 4 huevos, 500 ml de leche, 100 g de azúcar\nPasos:\n1. Haz caramelo 5 min.\n2. Hornea 45 minutos.")
    assert len(d["ingredientes"]) == 3 and d["tiempo_total_min"] == 50


def test_english_caption():
    d = parse_caption("Chickpea curry\nServes 4\nIngredients:\n- 2 tbsp curry paste\n- 1 onion\nMethod:\n1. Fry the onion 5 min.")
    assert d["raciones"] == 4 and d["ingredientes"][0]["unidad"] == "cda" and len(d["pasos"]) == 1


def test_no_recipe_in_caption():
    d = parse_caption("El brownie más fácil 😍 ¡Comenta BROWNIE y te la mando! #postres")
    assert d["tipo"] == "solo_video" and d["ingredientes"] == [] and d["titulo"].startswith("El brownie")


def test_numbered_lines_without_headers():
    d = parse_caption("Salmón al horno\n- 2 lomos de salmón\n- 1 calabacín\n1. Corta las verduras.\n2. Hornea 18 minutos.")
    assert len(d["ingredientes"]) == 2 and len(d["pasos"]) == 2
