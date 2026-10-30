from conftest import SEED


def test_migration_is_lossless(client, services, legacy):
    meta = client.get("/api/meta").json()
    assert meta["recetas"] == 62 and meta["solo_video"] == 73
    rebuilt = services.recipes.legacy_document()
    assert rebuilt == legacy  # every original key/value survives the migration


def test_solo_video_become_pending_recipes(client):
    pend = client.get("/api/recipes", params={"estado": "pendiente de transcribir"}).json()
    assert len(pend) == 73 and all(r["estado"] == "pendiente de transcribir" for r in pend)


def test_search_accent_and_typo_tolerant(client):
    a = client.get("/api/recipes", params={"q": "jamon"}).json()
    b = client.get("/api/recipes", params={"q": "jamón"}).json()
    assert a == b and len(a) > 0
    typo = client.get("/api/recipes", params={"q": "brochettas kebab"}).json()
    assert any("kebab" in r["titulo"].lower() for r in typo)


def test_filters_and_sorting(client):
    fast = client.get("/api/recipes", params={"tipo": "receta", "max_min": 30, "orden": "rapidas"}).json()
    assert fast and all(r["tiempo_total_min"] <= 30 for r in fast)
    assert [r["tiempo_total_min"] for r in fast] == sorted(r["tiempo_total_min"] for r in fast)
    cheap = client.get("/api/recipes", params={"tipo": "receta", "max_precio": 2, "orden": "baratas"}).json()
    assert all(r["precio_racion_eur"] <= 2 for r in cheap)
    tags = client.get("/api/tags").json()
    tag = tags[0]["etiqueta"]
    assert all(tag in r["etiquetas"] for r in client.get("/api/recipes", params={"etiqueta": tag}).json())


def test_crud_and_validation(client):
    body = {"titulo": "Tortilla francesa", "raciones": 1, "ingredientes": [
        {"nombre": "huevos", "cantidad_num": 2, "unidad": "ud", "precio_eur": 0.5}],
        "pasos": [{"texto": "Bate y cuaja.", "minutos": 4}]}
    r = client.post("/api/recipes", json=body)
    assert r.status_code == 201
    rec = r.json()
    assert rec["precio_total_eur"] == 0.5 and rec["tiempo_total_min"] == 4 and rec["estado"] == "completa"
    assert "huevo" in rec["alergenos"]
    rid = rec["id"]
    upd = client.put(f"/api/recipes/{rid}", json={**body, "titulo": "Tortilla francesa jugosa"}).json()
    assert upd["titulo"] == "Tortilla francesa jugosa" and upd["creado"] == rec["creado"]
    assert client.patch(f"/api/recipes/{rid}", json={"favorito": True, "valoracion": 5}).json()["favorito"] is True
    assert client.post(f"/api/recipes/{rid}/cocinado", json={"fecha": "2026-10-29", "notas": "Top"}).json()["cocinado"][0]["notas"] == "Top"
    assert client.post("/api/recipes", json={"titulo": ""}).status_code == 422
    assert client.post("/api/recipes", json={"titulo": "x", "video_url": "javascript:alert(1)"}).status_code == 422
    assert client.post("/api/recipes", json={"titulo": "x", "raciones": 0}).status_code == 422
    assert client.delete(f"/api/recipes/{rid}").status_code == 204
    assert client.get(f"/api/recipes/{rid}").status_code == 404


def test_duplicate_shortcode_rejected(client):
    r = client.post("/api/recipes", json={"titulo": "dup", "video_url": "https://www.instagram.com/x/reel/DPpn4clj0eC/"})
    assert r.status_code == 409 and r.json()["receta_id"] == 1


def test_missing_video_is_null_and_legacy_video_path_works(client, settings):
    assert client.get("/api/recipes/1").json()["media"]["video"] is None
    (settings.videos_dir / "DPpn4clj0eC.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 100)
    rec = client.get("/api/recipes/1").json()
    assert rec["media"]["video"] == "/videos/DPpn4clj0eC.mp4"
    res = client.get("/videos/DPpn4clj0eC.mp4", headers={"Range": "bytes=0-9"})
    assert res.status_code == 206 and len(res.content) == 10
