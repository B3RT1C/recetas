from app.services import units as U
from app.services.shopping import guess_category_name


def test_repollo_is_not_chicken():
    assert guess_category_name("repollo") != "Carne"
    assert guess_category_name("pechuga de pollo") == "Carne"


def test_size_words_merge():
    assert U.norm_name("Huevos L") == U.norm_name("huevo") == U.norm_name("huevos grandes")
    assert U.norm_name("cebolla mediana") == U.norm_name("Cebollas")
    assert U.norm_name("calabacín pequeño") == U.norm_name("calabacín")


def test_count_units_pluralised():
    assert U.display(2, "diente") == "2 dientes"
    assert U.display(1, "diente") == "1 diente"
    assert U.display(3, "loncha") == "3 lonchas"
    assert U.display(2, "ud") == "2"
    assert U.display(1500, "g") == "1,5 kg"


def test_price_history_records_changes_only(services):
    from app.services.prices import PriceEntry
    pc = services.prices
    for v in (2.0, 2.0, 2.5):
        pc.put(PriceEntry(ingredient="Tomate", supermarket="", price_per_kg=v, source="manual", fetched_at=""))
    rows = services.db.query("SELECT price_per_kg FROM price_history WHERE ingredient='tomate' ORDER BY id")
    assert [r[0] for r in rows] == [2.0, 2.5]
