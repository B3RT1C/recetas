from datetime import date, timedelta

from tests.test_shopping import mk


def test_week_add_move_servings_delete(client):
    r = mk(client)
    wk = client.get("/api/plan?inicio=2026-11-04").json()
    assert wk["inicio"] == "2026-11-02" and len(wk["dias"]) == 7 and wk["siguiente"] == "2026-11-09"
    p = client.post("/api/plan", json={"fecha": "2026-11-02", "comida": "cena", "receta_id": r["id"]}).json()
    assert p["raciones"] == 4 and p["titulo"] == "Bizcocho"
    p2 = client.post("/api/plan", json={"fecha": "2026-11-03", "comida": "comida", "receta_id": r["id"], "raciones": 2}).json()
    # move (drag & drop or keyboard alternative both use PATCH)
    m = client.patch(f"/api/plan/{p['id']}", json={"fecha": "2026-11-03", "comida": "comida", "posicion": 0}).json()
    assert (m["fecha"], m["comida"], m["posicion"]) == ("2026-11-03", "comida", 0)
    assert client.get(f"/api/plan?inicio=2026-11-02").json()["items"][0]["id"] == p["id"]
    assert client.patch(f"/api/plan/{p2['id']}", json={"raciones": 6}).json()["raciones"] == 6
    assert client.post("/api/plan", json={"fecha": "2026-11-02", "comida": "merienda", "receta_id": r["id"]}).status_code == 422
    assert client.post("/api/plan", json={"fecha": "2026-11-02", "receta_id": 99999}).status_code == 404
    assert client.delete(f"/api/plan/{p2['id']}").status_code == 204
    assert len(client.get("/api/plan?inicio=2026-11-02").json()["items"]) == 1


def test_week_to_shopping_list(client):
    r = mk(client)
    client.post("/api/plan", json={"fecha": "2026-11-02", "comida": "cena", "receta_id": r["id"], "raciones": 4})
    client.post("/api/plan", json={"fecha": "2026-11-05", "comida": "comida", "receta_id": r["id"], "raciones": 2})
    client.post("/api/plan", json={"fecha": "2026-11-20", "comida": "comida", "receta_id": r["id"], "raciones": 8})
    lst = client.post("/api/plan/a-lista", json={"inicio": "2026-11-02", "fin": "2026-11-08"}).json()
    assert lst["recetas_añadidas"] == 2
    huevos = next(i for i in lst["items"] if i["nombre"] == "Huevos")
    assert huevos["cantidad"] == 4.5 and huevos["texto_cantidad"] == "5"


def test_deleting_recipe_removes_plan_entries(client):
    r = mk(client)
    client.post("/api/plan", json={"fecha": date.today().isoformat(), "receta_id": r["id"]})
    client.delete(f"/api/recipes/{r['id']}")
    assert client.get("/api/plan").json()["items"] == []


def test_scale_endpoint(client):
    r = mk(client)
    s = client.get(f"/api/recipes/{r['id']}/escalar?raciones=2").json()
    ing = {i["nombre"]: i for i in s["ingredientes"]}
    assert ing["Huevos"]["cantidad"] == 2 and ing["Huevos"]["redondeado"]
    assert ing["Harina"]["texto"] == "½ taza" and ing["Azúcar"]["texto"] == "50 g"
