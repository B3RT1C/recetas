"""Unit conversion for scaling and shopping-list aggregation.

Kitchen measures (taza, cda, cdta, vaso...) become ml; mass units become g. When a density is
known for the ingredient, volumes of *solid* ingredients (harina, azúcar, arroz...) are turned
into grams too, so "1 taza de harina" and "200 g de harina" add up. Count units (ud, diente,
loncha...) stay as counts; whole items such as eggs are rounded to whole numbers.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Optional

MASS = {"g": 1, "gr": 1, "gramo": 1, "gramos": 1, "grs": 1, "kg": 1000, "kilo": 1000, "kilos": 1000, "mg": 0.001}
VOLUME = {"ml": 1, "cl": 10, "dl": 100, "l": 1000, "litro": 1000, "litros": 1000,
          "taza": 240, "tazas": 240, "vaso": 200, "vasos": 200,
          "cda": 15, "cdas": 15, "cucharada": 15, "cucharadas": 15,
          "cdta": 5, "cdtas": 5, "cucharadita": 5, "cucharaditas": 5, "chorrito": 10, "chorro": 15}
# Count units normalised to one spelling.
COUNT = {"ud": "ud", "uds": "ud", "unidad": "ud", "unidades": "ud", "u": "ud", "": "ud",
         "diente": "diente", "dientes": "diente", "diente(s)": "diente",
         "loncha": "loncha", "lonchas": "loncha", "rebanada": "rebanada", "rebanadas": "rebanada",
         "lata": "lata", "latas": "lata", "sobre": "sobre", "sobres": "sobre", "pizca": "pizca", "pizcas": "pizca",
         "puñado": "puñado", "puñados": "puñado", "manojo": "manojo", "ramita": "ramita", "ramitas": "ramita",
         "trozo": "trozo", "trozos": "trozo", "rodaja": "rodaja", "rodajas": "rodaja", "lámina": "lámina",
         "hoja": "hoja", "hojas": "hoja", "paquete": "paquete", "bolsa": "bolsa", "bote": "bote", "tarro": "tarro"}
# g per ml. Only entries flagged solid are converted ml -> g for aggregation.
DENSITY: list[tuple[str, float, bool]] = [
    ("harina", 0.53, True), ("maicena", 0.54, True), ("azucar glas", 0.5, True), ("azucar", 0.85, True),
    ("sal", 1.2, True), ("arroz", 0.8, True), ("avena", 0.38, True), ("cacao", 0.42, True),
    ("pan rallado", 0.45, True), ("queso rallado", 0.4, True), ("parmesano", 0.4, True), ("levadura", 0.8, True),
    ("mantequilla", 0.96, True), ("miel", 1.42, True), ("almendra molida", 0.4, True), ("coco rallado", 0.35, True),
    ("bicarbonato", 0.9, True), ("pimenton", 0.45, True), ("comino", 0.45, True), ("canela", 0.5, True),
    ("aceite", 0.92, False), ("leche", 1.03, False), ("nata", 1.0, False), ("agua", 1.0, False),
    ("caldo", 1.0, False), ("vino", 1.0, False), ("salsa de soja", 1.1, False), ("vinagre", 1.0, False),
    ("tomate triturado", 1.05, False), ("yogur", 1.05, False),
]
WHOLE_RE = re.compile(r"\b(huevos?|yemas?|claras?|pechugas?|muslos?|latas?|sobres?|aguacates?|limon(es)?|"
                      r"cebollas?|patatas?|pimientos?|calabacin(es)?|berenjenas?|tomates?|zanahorias?|platanos?|manzanas?)\b")
PREP_RE = re.compile(r"\b(picad[oa]s?|troceado?s?|en dados|en tiras|laminad[oa]s?|cortad[oa]s?|fresc[oa]s?|"
                     r"pelad[oa]s?|grande?s?|pequeñ[oa]s?|mediano?s?|maduro?s?|al gusto|opcional|"
                     r"en rodajas|finamente|machacad[oa]s?|rallad[oa]s? fino)\b")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


SIZE_WORDS = {"l", "m", "s", "xl", "xxl", "grande", "grandes", "mediano", "mediana", "medianos", "medianas",
              "pequeno", "pequena", "pequenos", "pequenas", "pequeño", "pequeña", "pequeños", "pequeñas"}

# count units that read better pluralised ("2 dientes", not "2 diente")
COUNT_PLURALS = {"diente": "dientes", "loncha": "lonchas", "pizca": "pizcas", "lamina": "láminas",
                 "lámina": "láminas", "hoja": "hojas", "rodaja": "rodajas", "rama": "ramas", "ramita": "ramitas",
                 "puñado": "puñados", "punado": "puñados", "taza": "tazas", "vaso": "vasos", "lata": "latas",
                 "sobre": "sobres", "filete": "filetes", "trozo": "trozos", "cabeza": "cabezas", "chorrito": "chorritos",
                 "hebra": "hebras", "bola": "bolas", "paquete": "paquetes", "tarro": "tarros", "manojo": "manojos"}


def norm_name(name: str) -> str:
    """Aggregation key: lowercase, no accents, no prep words or parentheses, simple singular."""
    s = strip_accents((name or "").lower())
    s = re.sub(r"\(.*?\)", " ", s)
    s = PREP_RE.sub(" ", s)
    s = re.sub(r"[^a-z0-9ñ ]+", " ", s)
    words = []
    for w in s.split():
        if w in SIZE_WORDS:  # "huevo L" and "huevo grande" are the same item
            continue
        if len(w) > 4 and w.endswith("es") and w[-3] in "lnrdjy":
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.append(w)
    return " ".join(words).strip()


def density_for(name: str) -> Optional[tuple[float, bool]]:
    n = strip_accents((name or "").lower())
    for key, d, solid in DENSITY:
        if key in n:
            return d, solid
    return None


def unit_kind(unit: str) -> str:
    u = strip_accents((unit or "").lower().strip().rstrip("."))
    u = {"cucharadita": "cdta", "cucharada": "cda"}.get(u, u)
    if u in MASS:
        return "mass"
    if u in VOLUME or strip_accents(u) in VOLUME:
        return "volume"
    return "count"


def _key(unit: str) -> str:
    return strip_accents((unit or "").lower().strip().rstrip("."))


def canonical(qty: Optional[float], unit: str, name: str = "") -> tuple[Optional[float], str]:
    """Convert to the unit used for aggregation: g, ml or a normalised count unit."""
    u = _key(unit)
    if u in MASS:
        return (None if qty is None else qty * MASS[u]), "g"
    if u in VOLUME:
        ml = None if qty is None else qty * VOLUME[u]
        d = density_for(name)
        if d and d[1]:
            return (None if ml is None else ml * d[0]), "g"
        return ml, "ml"
    raw = (unit or "").lower().strip()
    return qty, COUNT.get(raw, COUNT.get(u, raw or "ud"))


def convert(qty: float, from_unit: str, to_unit: str, name: str = "") -> Optional[float]:
    """Convert between any two units (None if impossible, e.g. ud -> g)."""
    fk, tk = _key(from_unit), _key(to_unit)
    if fk == tk:
        return qty
    def to_base(q, k):  # -> (value, 'g'|'ml')
        if k in MASS:
            return q * MASS[k], "g"
        if k in VOLUME:
            return q * VOLUME[k], "ml"
        return None, None
    v, base = to_base(qty, fk)
    if v is None:
        return None
    tgt = "g" if tk in MASS else "ml" if tk in VOLUME else None
    if tgt is None:
        return None
    if base != tgt:
        d = density_for(name)
        if not d:
            return None
        v = v * d[0] if base == "ml" else v / d[0]
    return v / (MASS[tk] if tgt == "g" else VOLUME[tk])


def is_whole(name: str, unit: str) -> bool:
    c = canonical(1, unit, name)[1]
    return c in ("ud", "diente", "lata", "sobre") or bool(WHOLE_RE.search(strip_accents((name or "").lower())))


def _r(x: float) -> float:
    return float(math.floor(x + 0.5))  # half up (Python's round() is banker's rounding)


def round_qty(qty: Optional[float], unit: str, name: str = "") -> tuple[Optional[float], bool]:
    """Smart rounding. Returns (value, rounded?)."""
    if qty is None:
        return None, False
    u = canonical(1, unit, name)[1] if unit_kind(unit) == "count" else _key(unit)
    if unit_kind(unit) == "count":
        if re.search(r"\bhuevos?\b", strip_accents((name or "").lower())):
            r = max(1.0, _r(qty))
        elif is_whole(name, unit):
            r = max(0.5, _r(qty * 2) / 2) if qty < 2 else _r(qty)
        elif u in ("pizca", "puñado", "manojo", "ramita"):
            r = max(1.0, _r(qty))
        else:
            r = _r(qty * 4) / 4 if qty < 3 else _r(qty)
    elif u in ("cda", "cdta", "taza", "vaso", "cdas", "cdtas", "tazas"):
        r = max(0.25, _r(qty * 4) / 4)
    elif u in ("g", "ml"):
        step = 1 if qty < 20 else 5 if qty < 200 else 10 if qty < 5000 else 50
        r = max(step, _r(qty / step) * step) if qty >= 1 else round(qty, 1)
    elif u in ("kg", "l"):
        r = round(qty, 2)
    else:
        r = round(qty, 2)
    return r, abs(r - qty) > 1e-6 and abs(r - qty) / max(qty, 1e-9) > 0.02


FRACTIONS = [(0.25, "¼"), (0.5, "½"), (0.75, "¾"), (1 / 3, "⅓"), (2 / 3, "⅔")]


def fmt_number(n: float) -> str:
    if n >= 10:
        return str(int(round(n)))
    w = math.floor(n)
    f = n - w
    for v, s in FRACTIONS:
        if abs(f - v) < 0.04:
            return f"{w or ''}{s}"
    return (f"{n:.1f}".rstrip("0").rstrip(".")).replace(".", ",")


def display(qty: Optional[float], unit: str) -> str:
    """Human text; big g/ml become kg/l."""
    if qty is None:
        return ""
    u = unit
    if u == "g" and qty >= 1000:
        qty, u = qty / 1000, "kg"
    elif u == "ml" and qty >= 1000:
        qty, u = qty / 1000, "l"
    num = (f"{qty:.2f}".rstrip("0").rstrip(".").replace(".", ",")) if u in ("kg", "l") else fmt_number(qty)
    if u == "ud":
        return num
    if qty > 1 and u in COUNT_PLURALS:
        u = COUNT_PLURALS[u]
    return f"{num} {u}"


def scale_ingredient(ing: dict, factor: float) -> dict:
    """Scale one recipe ingredient. Keeps the recipe's own unit (cda stays cda) and rounds smartly."""
    q = ing.get("cantidad_num")
    unit = ing.get("unidad") or "ud"
    out = {"nombre": ing.get("nombre", ""), "unidad": unit, "cantidad": None, "texto": "", "redondeado": False}
    if q is None:
        out["texto"] = ing.get("cantidad_normal") or "al gusto"
        return out
    raw = q * factor
    val, rounded = round_qty(raw, unit, out["nombre"]) if factor != 1 else (raw, False)
    out.update(cantidad=val, redondeado=rounded, texto=display(val, unit))
    if ing.get("precio_eur") is not None:
        out["precio_eur"] = round(ing["precio_eur"] * factor, 2)
    return out


def scale_recipe(recipe: dict, servings: float) -> dict:
    base = recipe.get("raciones") or 1
    k = servings / base
    return {"raciones": servings, "factor": k,
            "ingredientes": [scale_ingredient(i, k) for i in recipe.get("ingredientes") or []],
            "precio_total_eur": None if recipe.get("precio_total_eur") is None else round(recipe["precio_total_eur"] * k, 2)}
