"""Heuristic, Spanish-aware parser: Instagram caption -> recipe draft.

It is deliberately conservative: everything it cannot read with confidence is
left empty and the draft is always reviewed by the user before saving.
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction
from typing import Optional

from .tags import norm, suggest_tags

ING_HEADERS = ("ingredientes", "ingrediente", "ingredients", "necesitas", "lista de la compra", "para la salsa", "para la masa")
STEP_HEADERS = ("preparacion", "elaboracion", "pasos", "instrucciones", "modo de preparacion", "como se hace",
                "procedimiento", "method", "instructions", "directions", "steps", "receta")
STOP_HEADERS = ("notas", "nota", "tips", "consejos", "trucos")

UNITS = {
    "g": "g", "gr": "g", "grs": "g", "gramo": "g", "gramos": "g", "kg": "kg", "kilo": "kg", "kilos": "kg",
    "ml": "ml", "l": "l", "litro": "l", "litros": "l", "cl": "cl", "dl": "dl",
    "cda": "cda", "cdas": "cda", "cucharada": "cda", "cucharadas": "cda", "tbsp": "cda", "cs": "cda",
    "cdta": "cdta", "cdtas": "cdta", "cucharadita": "cdta", "cucharaditas": "cdta", "tsp": "cdta", "cc": "cdta",
    "taza": "taza", "tazas": "taza", "cup": "taza", "cups": "taza", "vaso": "vaso", "vasos": "vaso",
    "diente": "diente", "dientes": "diente", "pizca": "pizca", "pizcas": "pizca", "puñado": "puñado", "puñados": "puñado",
    "lata": "lata", "latas": "lata", "sobre": "sobre", "sobres": "sobre", "loncha": "lonchas", "lonchas": "lonchas",
    "rebanada": "rebanada", "rebanadas": "rebanada", "rodaja": "rodaja", "rodajas": "rodaja", "ramita": "ramita",
    "ramitas": "ramita", "manojo": "manojo", "chorrito": "chorrito", "chorro": "chorrito", "oz": "oz", "lb": "lb",
}
WORD_NUMBERS = {"un": 1, "una": 1, "uno": 1, "medio": 0.5, "media": 0.5, "dos": 2, "tres": 3, "cuatro": 4,
                "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "doce": 12}
UNICODE_FRACTIONS = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3"}

BULLET_RE = re.compile(r"^\s*(?:[-–—•·*▪►✔✅☑️➡️👉🔸🔹]+|\d{1,2}\s*[.)º°-]|\d{1,2}️⃣|paso\s*\d+\s*[:.-]?)\s*", re.I)
NUM_STEP_RE = re.compile(r"^\s*(?:\d{1,2}\s*[.)º°-]|\d{1,2}️⃣|paso\s*\d+)", re.I)
QTY_RE = re.compile(
    r"^(?P<num>\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?(?:\s+\d/\d)?|\d+\s*-\s*\d+)\s*(?P<unit>[a-zñáéíóú]+\.?)?\s*(?:de\s+)?(?P<name>.*)$",
    re.I,
)
TRAILING_QTY_RE = re.compile(r"^(?P<name>.+?)[\s:,-]+(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>[a-zñ]+)\.?$", re.I)
MIN_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:-\s*\d+\s*)?(min(?:uto)?s?|h(?:ora)?s?)\b", re.I)
SERVES_RE = re.compile(r"(?:para|raciones|porciones|personas|serves|servings)\D{0,15}(\d{1,2})|(\d{1,2})\s*(?:raciones|personas|porciones|servings)", re.I)
HASHTAG_RE = re.compile(r"(?:#|@)[\w.áéíóúñü]+", re.I)
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d\u20e3]+")


def _clean(line: str) -> str:
    line = EMOJI_RE.sub(" ", line)
    return re.sub(r"\s+", " ", line).strip(" :-–—•*.")


def _header_kind(line: str) -> Optional[str]:
    head = line.split(":", 1)[0] if ":" in line else line
    n = norm(_clean(head)).strip(" :")
    if not n or len(n) > 40:
        return None
    for kind, words in (("ing", ING_HEADERS), ("steps", STEP_HEADERS), ("stop", STOP_HEADERS)):
        if any(n == w or n.startswith(w + " ") or n.startswith(w + ":") for w in words):
            return kind
    return None


def _to_number(raw: str) -> Optional[float]:
    raw = raw.strip().replace(",", ".")
    try:
        if "-" in raw:  # range "2-3" -> upper bound
            return float(raw.split("-")[-1])
        parts = raw.split()
        return float(sum(Fraction(p.replace(" ", "")) for p in parts))
    except (ValueError, ZeroDivisionError):
        return None


def parse_ingredient(line: str) -> dict:
    text = _clean(line)
    for k, v in UNICODE_FRACTIONS.items():
        text = text.replace(k, " " + v)
    text = text.strip()
    first = norm(text.split(" ")[0]) if text else ""
    if first in WORD_NUMBERS:
        text = f"{WORD_NUMBERS[first]:g} " + text.split(" ", 1)[1] if " " in text else text
    ing = {"nombre": text, "cantidad_num": None, "unidad": "ud", "estimada": False, "precio_eur": None}
    m = QTY_RE.match(text)
    if m:
        num = _to_number(m.group("num"))
        unit_raw = (m.group("unit") or "").rstrip(".").lower()
        name = m.group("name").strip()
        if unit_raw and unit_raw in UNITS:
            unit = UNITS[unit_raw]
        else:
            unit = "ud"
            name = text[m.end("num"):].strip()
        if unit == "kg":
            unit, num = "g", num * 1000 if num is not None else None
        elif unit == "l":
            unit, num = "ml", num * 1000 if num is not None else None
        elif unit == "cl":
            unit, num = "ml", num * 10 if num is not None else None
        ing.update(nombre=re.sub(r"^de\s+", "", name, flags=re.I) or text, cantidad_num=num, unidad=unit)
    else:
        t = TRAILING_QTY_RE.match(text)
        if t and t.group("unit").lower() in UNITS:
            ing.update(nombre=t.group("name").strip(), cantidad_num=_to_number(t.group("num")), unidad=UNITS[t.group("unit").lower()])
    if ing["cantidad_num"] is None:
        ing["estimada"] = True  # "al gusto", "sal", ...
    ing["nombre"] = ing["nombre"][:1].lower() + ing["nombre"][1:] if ing["nombre"] else ing["nombre"]
    return ing


def _minutes(text: str) -> Optional[int]:
    total = 0.0
    found = False
    for num, unit in MIN_RE.findall(text):
        found = True
        value = float(num.replace(",", "."))
        total += value * 60 if unit.lower().startswith("h") else value
    return int(round(total)) if found else None


def _title(lines: list[str]) -> str:
    for line in lines:
        c = _clean(HASHTAG_RE.sub("", line))
        if c and not _header_kind(line) and len(c) >= 3:
            c = re.split(r"[.!?¡¿]\s", c)[0]
            c = c[:90].strip(" !¡")
            letters = [ch for ch in c if ch.isalpha()]
            if letters and sum(ch.isupper() for ch in letters) / len(letters) > 0.6:
                c = c.lower().capitalize()
            return c
    return "Receta sin título"


def parse_caption(caption: str, *, autor: str = "", video_url: str = "") -> dict:
    caption = unicodedata.normalize("NFC", caption or "")
    raw_lines = [l for l in caption.replace("\r", "").split("\n")]
    lines = [l for l in raw_lines if _clean(HASHTAG_RE.sub("", l))]
    section: Optional[str] = None
    ingredients: list[dict] = []
    steps: list[dict] = []
    notes: list[str] = []
    intro: list[str] = []
    for line in lines:
        kind = _header_kind(line)
        if kind:
            section = kind
            # "Ingredientes: harina, huevos" on the same line
            rest = line.split(":", 1)[1] if ":" in line else ""
            if rest.strip() and kind == "ing":
                ingredients += [parse_ingredient(p) for p in re.split(r",|;", rest) if _clean(p)]
            continue
        text = HASHTAG_RE.sub("", line) if section != "ing" else line
        if not _clean(text):
            continue
        if section == "ing":
            if NUM_STEP_RE.match(line) and len(_clean(line)) > 60:  # long numbered line -> steps started
                section = "steps"
            else:
                ingredients.append(parse_ingredient(BULLET_RE.sub("", line)))
                continue
        if section == "steps":
            body = _clean(BULLET_RE.sub("", text))
            if body:
                steps.append({"texto": body[0].upper() + body[1:], "minutos": _minutes(body)})
            continue
        if section == "stop":
            notes.append(_clean(text))
            continue
        intro.append(line)
    # No explicit sections: numbered lines are steps, short bullet lines with numbers are ingredients
    if not ingredients and not steps:
        for line in intro[1:]:
            body = _clean(BULLET_RE.sub("", HASHTAG_RE.sub("", line)))
            if not body:
                continue
            if NUM_STEP_RE.match(line):
                steps.append({"texto": body[0].upper() + body[1:], "minutos": _minutes(body)})
            elif BULLET_RE.match(line) and len(body) < 60:
                ingredients.append(parse_ingredient(body))
    serves = None
    m = SERVES_RE.search(norm(caption))
    if m:
        serves = int(m.group(1) or m.group(2))
    draft = {
        "tipo": "receta" if (ingredients or steps) else "solo_video",
        "titulo": _title(raw_lines),
        "autor": autor,
        "video_url": video_url,
        "raciones": serves or 2,
        "raciones_estimadas": serves is None,
        "ingredientes": ingredients,
        "pasos": steps,
        "notas": " ".join(n for n in notes if n),
        "pasos_sugeridos": False,
        "nota": "" if (ingredients or steps) else "La descripción no trae receta; revisa el vídeo.",
    }
    if steps and all(s["minutos"] is not None for s in steps):
        draft["tiempo_total_min"] = sum(s["minutos"] for s in steps)
    draft["etiquetas"] = suggest_tags(draft)
    return draft
