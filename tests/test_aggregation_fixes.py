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
