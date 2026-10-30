"""Fill a running demo server (started with RECETAS_SEED_FILE=data/sample/recetas-demo.json) with a
realistic week: a plan for 2-4 people, two shopping lists, a small pantry and a few favourites.

Used for screenshots only. Covers come from data/sample/covers (copied to <media>/covers by the caller).
    python scripts/seed_demo.py --base http://127.0.0.1:8137 --user admin --password-stdin
"""
import argparse
import http.cookiejar
import json
import sys
import urllib.request
from datetime import date, timedelta

# (day offset from Monday, meal, recipe title, servings) - a normal household week, not every slot filled
PLAN = [
    (0, "comida", "Lentejas estofadas", 4), (0, "cena", "Crema de calabaza", 2),
    (1, "comida", "Macarrones con tomate", 3), (1, "cena", "Tortilla de patatas", 2),
    (2, "comida", "Pollo asado con patatas", 4), (2, "cena", "Ensalada de garbanzos", 2),
    (3, "comida", "Salmorejo cordobés", 2), (3, "cena", "Merluza al horno con ensalada", 2),
    (4, "cena", "Croquetas de jamón", 4),
    (5, "comida", "Paella de marisco", 4), (6, "comida", "Arroz con leche", 4),
]
FAVS = ["Tortilla de patatas", "Paella de marisco", "Lentejas estofadas", "Flan de huevo"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8137")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password-stdin", action="store_true", required=True)
    ap.add_argument("--week", default=None, help="any date of the week to plan (default: this week)")
    a = ap.parse_args()
    pw = sys.stdin.readline().rstrip("\n")
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    hdr = {"Content-Type": "application/json"}

    def call(method, path, body=None):
        req = urllib.request.Request(a.base + path, method=method, headers=hdr,
                                     data=None if body is None else json.dumps(body).encode())
        with op.open(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None

    hdr["X-CSRF-Token"] = call("POST", "/api/auth/login", {"username": a.user, "password": pw})["csrf"]
    recetas = {r["titulo"]: r["id"] for r in call("GET", "/api/recipes")}
    d = date.fromisoformat(a.week) if a.week else date.today()
    mon = d - timedelta(days=d.weekday())
    for off, comida, titulo, n in PLAN:
        call("POST", "/api/plan", {"fecha": (mon + timedelta(days=off)).isoformat(), "comida": comida,
                                   "receta_id": recetas[titulo], "raciones": n})
    for t in FAVS:
        call("PATCH", f"/api/recipes/{recetas[t]}", {"favorito": True})
    for p in ("sal", "aceite de oliva", "azúcar"):
        call("POST", "/api/compra/despensa", {"nombre": p})
    lst = call("POST", "/api/compra/listas", {"nombre": "Lista de la compra"})
    call("POST", "/api/plan/a-lista", {"inicio": mon.isoformat(), "fin": (mon + timedelta(days=6)).isoformat(),
                                       "lista_id": lst["id"]})
    call("POST", f"/api/compra/listas/{lst['id']}/items", {"nombre": "Papel de cocina", "cantidad": 1, "unidad": "ud"})
    call("POST", f"/api/compra/listas/{lst['id']}/items", {"nombre": "Café molido", "cantidad": 250, "unidad": "g"})
    fin = call("POST", "/api/compra/listas", {"nombre": "Cena del sábado"})
    call("POST", f"/api/compra/listas/{fin['id']}/receta", {"receta_id": recetas["Flan de huevo"], "raciones": 6})
    print(f"demo: {len(PLAN)} entradas de plan, semana del {mon.isoformat()}")


if __name__ == "__main__":
    main()
