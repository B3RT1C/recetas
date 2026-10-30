from urllib.parse import unquote

RECIPE = {"titulo": "Bizcocho", "raciones": 4, "ingredientes": [
    {"nombre": "Harina", "cantidad_num": 1, "unidad": "taza", "precio_eur": 0.2},
    {"nombre": "Huevos", "cantidad_num": 3, "unidad": "ud", "precio_eur": 0.75},
    {"nombre": "Azúcar", "cantidad_num": 100, "unidad": "g"},
    {"nombre": "Sal", "cantidad_num": None, "cantidad_normal": "una pizca", "unidad": ""}]}


def mk(client, data=RECIPE):
    return client.post("/api/recipes", json=data).json()


def test_list_crud_and_manual_items(client):
    lst = client.post("/api/compra/listas", json={"nombre": "Semana"}).json()
    lid = lst["id"]
    it = client.post(f"/api/compra/listas/{lid}/items", json={"nombre": "Cebollas", "cantidad": 2, "unidad": "ud"}).json()
    assert it["texto_cantidad"] == "2" and it["estado"] == "pendiente"
    cats = {c["id"]: c["nombre"] for c in client.get("/api/compra/categorias").json()}
    assert cats[it["categoria_id"]] == "Fruta y verdura"
    # same item again merges
    it2 = client.post(f"/api/compra/listas/{lid}/items", json={"nombre": "cebolla", "cantidad": 1}).json()
    assert it2["id"] == it["id"] and it2["cantidad"] == 3
    # edit quantity + unit, note, state
    it3 = client.patch(f"/api/compra/items/{it['id']}", json={"cantidad": 1.5, "unidad": "kg", "nota": "moradas",
                                                              "estado": "comprado"}).json()
    assert it3["unidad"] == "g" and it3["cantidad"] == 1500 and it3["texto_cantidad"] == "1,5 kg"
    assert it3["nota"] == "moradas" and it3["estado"] == "comprado"
    assert client.patch(f"/api/compra/items/{it['id']}", json={"estado": "raro"}).status_code == 422
    assert client.get("/api/compra/listas").json()[0]["total"] == 1
    client.patch(f"/api/compra/listas/{lid}", json={"nombre": "Finde"})
    assert client.get(f"/api/compra/listas/{lid}").json()["nombre"] == "Finde"
    assert client.delete(f"/api/compra/listas/{lid}").status_code == 204
    assert client.get(f"/api/compra/listas/{lid}").status_code == 404


def test_add_recipe_aggregates_and_converts(client):
    r = mk(client)
    lid = client.post("/api/compra/listas", json={}).json()["id"]
    client.post(f"/api/compra/listas/{lid}/items", json={"nombre": "harina", "cantidad": 200, "unidad": "g"})
    lst = client.post(f"/api/compra/listas/{lid}/receta", json={"receta_id": r["id"], "raciones": 2}).json()
    by = {i["nombre"].lower(): i for i in lst["items"]}
    harina = by["harina"]
    assert harina["unidad"] == "g" and round(harina["cantidad"], 1) == round(200 + 0.5 * 240 * 0.53, 1)
    huevos = by["huevos"]
    assert huevos["cantidad"] == 1.5 and huevos["texto_cantidad"] == "2"   # smart rounding for display
    assert by["sal"]["cantidad"] is None
    # twice -> adds up, sources tracked
    lst = client.post(f"/api/compra/listas/{lid}/receta", json={"receta_id": r["id"], "raciones": 2}).json()
    huevos = next(i for i in lst["items"] if i["nombre"] == "Huevos")
    assert huevos["cantidad"] == 3 and len(huevos["origenes"]) == 2
    # orientative price (estimado), can be hidden
    assert lst["precio_fuente"] == "estimado" and lst["precio_estimado_eur"] > 0 and lst["precio_parcial"]
    hidden = client.patch(f"/api/compra/listas/{lid}", json={"mostrar_precios": False}).json()
    assert hidden["precio_estimado_eur"] is None and all(i["precio_eur"] is None for i in hidden["items"])
    # remove the recipe again
    lst = client.delete(f"/api/compra/listas/{lid}/receta/{r['id']}").json()
    names = [i["nombre"].lower() for i in lst["items"]]
    assert names == ["harina"] and round(lst["items"][0]["cantidad"]) == 200


def test_pantry_recurring_and_clear(client):
    client.post("/api/compra/despensa", json={"nombre": "Sal"})
    assert [p["nombre"] for p in client.get("/api/compra/despensa").json()] == ["Sal"]
    r = mk(client)
    lid = client.post("/api/compra/listas", json={}).json()["id"]
    lst = client.post(f"/api/compra/listas/{lid}/receta", json={"receta_id": r["id"]}).json()
    assert next(i for i in lst["items"] if i["nombre"] == "Sal")["estado"] == "ya_lo_tengo"
    leche = client.post(f"/api/compra/listas/{lid}/items", json={"nombre": "Leche", "cantidad": 2, "unidad": "l",
                                                                  "recurrente": True}).json()
    for i in lst["items"] + [leche]:
        client.patch(f"/api/compra/items/{i['id']}", json={"estado": "comprado"})
    lst = client.post(f"/api/compra/listas/{lid}/limpiar").json()
    assert [(i["nombre"], i["estado"]) for i in lst["items"]] == [("Leche", "pendiente")]


def test_categories_reorder_and_items_order(client):
    cats = client.get("/api/compra/categorias").json()
    ids = [c["id"] for c in cats][::-1]
    assert [c["id"] for c in client.post("/api/compra/categorias/orden", json={"ids": ids}).json()] == ids
    new = client.post("/api/compra/categorias", json={"nombre": "Mercado"}).json()
    assert client.post("/api/compra/categorias", json={"nombre": "Mercado"}).status_code == 422
    client.patch(f"/api/compra/categorias/{new['id']}", json={"nombre": "Mercadillo"})
    lid = client.post("/api/compra/listas", json={}).json()["id"]
    a = client.post(f"/api/compra/listas/{lid}/items", json={"nombre": "A", "categoria_id": new["id"]}).json()
    b = client.post(f"/api/compra/listas/{lid}/items", json={"nombre": "B", "categoria_id": new["id"]}).json()
    lst = client.post(f"/api/compra/listas/{lid}/orden", json={"ids": [b["id"], a["id"]]}).json()
    assert [i["nombre"] for i in lst["items"]] == ["B", "A"]
    assert client.delete(f"/api/compra/categorias/{new['id']}").status_code == 204
    assert client.get(f"/api/compra/items/{a['id']}").status_code in (404, 405)
    assert client.get(f"/api/compra/listas/{lid}").json()["items"][0]["categoria_id"] is None


def test_share_text_and_whatsapp(client):
    lid = client.post("/api/compra/listas", json={"nombre": "Cena"}).json()["id"]
    client.post(f"/api/compra/listas/{lid}/items", json={"nombre": "Tomates", "cantidad": 4, "nota": "maduros"})
    t = client.post(f"/api/compra/listas/{lid}/items", json={"nombre": "Pan"}).json()
    client.patch(f"/api/compra/items/{t['id']}", json={"estado": "ya_lo_tengo"})
    sh = client.get(f"/api/compra/listas/{lid}/compartir").json()
    assert "🛒 Cena" in sh["texto"] and "• 4 Tomates (maduros)" in sh["texto"] and "Pan" not in sh["texto"]
    assert sh["whatsapp"].startswith("https://wa.me/?text=") and unquote(sh["whatsapp"][20:]) == sh["texto"]
    assert "Pan" in client.get(f"/api/compra/listas/{lid}/compartir?incluir_tengo=true").json()["texto"]
