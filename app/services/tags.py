"""Heuristic, Spanish-aware tag suggestions used during migration and import."""
from __future__ import annotations

import re
import unicodedata

def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()

_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("pollo", ("pollo", "chicken", "pechuga", "muslo")),
    ("ternera", ("ternera", "vacuno", "beef", "carne picada", "galbi", "bistec", "solomillo de ternera")),
    ("cerdo", ("cerdo", "pork", "bacon", "beicon", "panceta", "chorizo", "jamon", "lomo", "costilla")),
    ("pescado y marisco", ("salmon", "atun", "bacalao", "merluza", "gamba", "langostino", "pescado", "marisco", "pulpo", "calamar", "mejillon", "shrimp")),
    ("pasta", ("pasta", "espagueti", "spaghetti", "macarrones", "tallarines", "lasana", "noodle", "fideo", "penne", "rigatoni", "gnocchi", "ramen")),
    ("arroz", ("arroz", "rice", "risotto", "paella")),
    ("huevos", ("huevo", "tortilla de patata", "egg")),
    ("postre", ("postre", "tarta", "bizcocho", "galleta", "brownie", "chocolate", "helado", "flan", "cookie", "dulce", "pastel", "cheesecake", "crepe", "tiramisu")),
    ("ensalada", ("ensalada", "salad")),
    ("sopa y crema", ("sopa", "crema de", "caldo", "soup")),
    ("horno", ("horno", "hornea", "gratinad", "asad", "al horno", "bake", "oven")),
    ("airfryer", ("airfryer", "air fryer", "freidora de aire")),
    ("sartén", ("sarten", "salte", "plancha")),
]

_ALLERGENS: list[tuple[str, tuple[str, ...]]] = [
    ("gluten", ("harina", "pan", "pasta", "espagueti", "macarrones", "tallarines", "tortilla de trigo", "tortillas", "cuscus", "trigo", "cebada", "centeno", "galleta", "lasana", "fideo", "noodle", "gnocchi", "pan rallado", "panko", "cerveza", "seitan", "bizcocho", "masa")),
    ("lácteos", ("leche", "nata", "queso", "mantequilla", "yogur", "parmesano", "mozzarella", "crema agria", "requeson", "ricotta", "mascarpone", "burrata")),
    ("huevo", ("huevo", "yema", "clara", "mayonesa")),
    ("pescado", ("salmon", "atun", "bacalao", "merluza", "anchoa", "pescado", "salsa de pescado", "sardina")),
    ("crustáceos", ("gamba", "langostino", "camaron", "shrimp", "cangrejo", "bogavante")),
    ("moluscos", ("mejillon", "almeja", "calamar", "pulpo", "sepia", "ostra")),
    ("frutos secos", ("almendra", "nuez", "nueces", "avellana", "anacardo", "pistacho", "pinones")),
    ("cacahuete", ("cacahuete", "mani", "peanut")),
    ("soja", ("soja", "tofu", "edamame", "miso", "tamari")),
    ("sésamo", ("sesamo", "tahini", "tahin")),
    ("mostaza", ("mostaza",)),
    ("apio", ("apio",)),
]


def suggest_allergens(recipe: dict) -> list[str]:
    """Heuristic allergen hints from ingredient names (always shown as an estimate)."""
    text = " ".join(norm(i.get("nombre", "")) for i in recipe.get("ingredientes") or [])
    return [a for a, words in _ALLERGENS if any(re.search(r"\b" + re.escape(w), text) for w in words)]
_MEAT = ("pollo", "ternera", "cerdo", "pescado y marisco")


def suggest_tags(recipe: dict) -> list[str]:
    title = norm(recipe.get("titulo", ""))
    ingredients = " ".join(norm(i.get("nombre", "")) for i in recipe.get("ingredientes") or [])
    steps = " ".join(norm(p.get("texto", "")) for p in recipe.get("pasos") or [])
    text = f"{title} {ingredients} {steps}"
    title_only = {"sopa y crema", "ensalada", "postre"}
    tags = [tag for tag, words in _RULES
            if any(re.search(r"\b" + re.escape(w), title if tag in title_only else text) for w in words)]
    if recipe.get("ingredientes") and not any(t in tags for t in _MEAT):
        tags.append("vegetariana")
    minutes = recipe.get("tiempo_total_min")
    if isinstance(minutes, (int, float)) and minutes <= 30:
        tags.append("rápida")
    price = recipe.get("precio_racion_eur")
    if isinstance(price, (int, float)) and price <= 1.5:
        tags.append("económica")
    return tags
