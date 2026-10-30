import logging

from conftest import wait_job


def login(client):
    r = client.post("/api/instagram/login", json={"username": "chef", "password": "s3cret-pass"})
    assert r.status_code == 200 and r.json()["estado"] == "ok"


def test_requires_login(client):
    r = client.get("/api/instagram/collections")
    assert r.status_code == 400 and "conecta" in r.json()["detail"]


def test_login_wrong_password(client):
    r = client.post("/api/instagram/login", json={"username": "a", "password": "incorrecta"})
    assert r.status_code == 400


def test_two_factor_flow(client):
    r = client.post("/api/instagram/login", json={"username": "chef2fa", "password": "x"}).json()
    assert r["estado"] == "2fa"
    assert client.post("/api/instagram/2fa", json={"code": "000000"}).status_code == 400
    assert client.post("/api/instagram/2fa", json={"code": "123456"}).json()["usuario"] == "chef2fa"
    assert client.get("/api/instagram/status").json()["conectado"] is True


def test_cookie_session_alternative(client):
    assert client.post("/api/instagram/cookies", json={"cookies": "csrftoken=a"}).status_code == 400
    assert client.post("/api/instagram/cookies", json={"sessionid": "abc%3A123"}).json()["estado"] == "ok"


def test_password_never_stored_or_logged(client, services, settings, caplog):
    caplog.set_level(logging.DEBUG)
    login(client)
    assert "s3cret-pass" not in caplog.text
    for f in settings.data_dir.rglob("*"):
        if f.is_file():
            assert b"s3cret-pass" not in f.read_bytes()
    for f in settings.secret_dir.rglob("*"):
        assert b"s3cret-pass" not in f.read_bytes()


def test_collections_posts_and_dedupe_flags(client):
    login(client)
    cols = client.get("/api/instagram/collections").json()
    assert [c["id"] for c in cols] == ["all", "C", "Postres"]
    posts = client.get("/api/instagram/collections/C/posts").json()
    by = {p["shortcode"]: p for p in posts}
    assert by["DPpn4clj0eC"]["estado"] == "importado"  # already in the recipe book
    assert by["MOCKpasta01"]["estado"] == "nuevo" and by["MOCKpasta01"]["miniatura"].startswith("data:image/svg")


def test_import_job_drafts_review_and_save(client, settings):
    login(client)
    items = [{"shortcode": "MOCKpasta01", "contenido": "ambos"}, {"shortcode": "MOCKbrown04", "contenido": "video"},
             {"shortcode": "MOCKtorti02", "contenido": "foto"}, {"shortcode": "DPpn4clj0eC", "contenido": "ambos"}]
    job = client.post("/api/instagram/import", json={"items": items})
    assert job.status_code == 202
    job = wait_job(client, job.json()["id"])
    st = {i["shortcode"]: i for i in job["items"]}
    assert job["progreso"] == 100
    assert st["MOCKpasta01"]["estado"] == "ok" and st["DPpn4clj0eC"]["estado"] == "duplicado"
    assert "sin vídeo" in st["MOCKbrown04"]["mensaje"]
    assert (settings.videos_dir / "MOCKpasta01.mp4").exists()  # legacy layout videos/CODE.mp4
    assert (settings.media_dir / "photos" / "MOCKpasta01.png").exists()
    assert not (settings.videos_dir / "MOCKtorti02.mp4").exists()
    drafts = client.get("/api/drafts").json()
    pasta = next(d for d in drafts if d["shortcode"] == "MOCKpasta01")
    assert pasta["metodo"] == "heuristico" and len(pasta["ingredientes"]) == 6
    # review + edit, then save
    edited = {**{k: v for k, v in pasta.items() if k not in ("id", "job_id", "shortcode", "creado")}, "titulo": "Pasta cremosa"}
    assert client.put(f"/api/drafts/{pasta['id']}", json=edited).json()["titulo"] == "Pasta cremosa"
    saved = client.post(f"/api/drafts/{pasta['id']}/save").json()
    assert saved["titulo"] == "Pasta cremosa" and saved["shortcode"] == "MOCKpasta01"
    assert saved["media"]["video"] == "/videos/MOCKpasta01.mp4" and saved["media"]["foto"] == "/media/photos/MOCKpasta01.png"
    posts = client.get("/api/instagram/collections/C/posts").json()
    assert next(p for p in posts if p["shortcode"] == "MOCKpasta01")["estado"] == "importado"
    # re-importing the same post is skipped
    job2 = wait_job(client, client.post("/api/instagram/import", json={"items": items[:1]}).json()["id"])
    assert job2["items"][0]["estado"] == "duplicado"


def test_import_uses_ai_when_configured_and_falls_back(client, services):
    from app.services.ai import FakeAIProvider
    login(client)
    services.ai.override = FakeAIProvider()
    job = wait_job(client, client.post("/api/instagram/import", json={"items": [{"shortcode": "MOCKflan06", "contenido": "foto"}]}).json()["id"])
    d = client.get(f"/api/drafts").json()[0]
    assert d["metodo"] == "ia" and d["titulo"] == "Receta extraída por IA"
    services.ai.override = FakeAIProvider(fail=True)
    wait_job(client, client.post("/api/instagram/import", json={"items": [{"shortcode": "MOCKsalmo03", "contenido": "foto"}]}).json()["id"])
    d2 = next(x for x in client.get("/api/drafts").json() if x["shortcode"] == "MOCKsalmo03")
    assert d2["metodo"] == "heuristico" and d2["ingredientes"]


def test_thumbnail_proxy_only_allows_instagram_cdn(client):
    assert client.get("/api/instagram/thumb", params={"u": "http://169.254.169.254/latest"}).status_code == 400
    assert client.get("/api/instagram/thumb", params={"u": "https://evil.com/cdninstagram.com/a.jpg"}).status_code == 400


def test_parse_caption_endpoint(client):
    r = client.post("/api/parse-caption", json={"caption": "Tostadas\nIngredientes\n- 2 rebanadas de pan"}).json()
    assert r["metodo"] == "heuristico" and r["receta"]["ingredientes"][0]["unidad"] == "rebanada"
