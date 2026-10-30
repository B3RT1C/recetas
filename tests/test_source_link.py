import json

import pytest

from app.services.source_link import source_of, source_type


@pytest.mark.parametrize("url,kind", [
    ("https://www.instagram.com/x/reel/ABC/", "instagram"),
    ("https://vm.tiktok.com/abc", "tiktok"),
    ("https://youtu.be/xyz", "youtube"),
    ("https://m.youtube.com/watch?v=1", "youtube"),
    ("https://www.recetasderechupete.com/receta/", "web"),
    ("https://notinstagram.com/p", "web"),
    ("", None), ("javascript:alert(1)", None), ("ftp://x/y", None),
])
def test_source_type(url, kind):
    assert source_type(url) == kind


def test_source_precedence_and_manual():
    assert source_of({"source_url": "https://youtu.be/a", "video_url": "https://www.instagram.com/reel/B/"}) == ("https://youtu.be/a", "youtube")
    assert source_of({}, "ABC") == ("https://www.instagram.com/reel/ABC/", "instagram")
    assert source_of({"video_url": ""}, None) == (None, None)


def _new(client, **kw):
    r = client.post("/api/recipes", json={"titulo": "Prueba", **kw})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_api_payloads_include_source(client):
    web = _new(client, source_url="https://www.example.com/tarta")
    manual = _new(client, titulo="Manual")
    r = client.get(f"/api/recipes/{web}").json()
    assert r["source_url"] == "https://www.example.com/tarta" and r["source_type"] == "web"
    m = client.get(f"/api/recipes/{manual}").json()
    assert m["source_url"] is None and m["source_type"] is None
    seeded = client.get("/api/recipes/1").json()
    assert seeded["source_type"] == "instagram" and seeded["source_url"].startswith("https://www.instagram.com/")
    assert client.post("/api/recipes", json={"titulo": "X", "source_url": "javascript:alert(1)"}).status_code == 422


def test_v1_and_mcp_include_source(client, services):
    from app.mcp_server import _summary
    tok = client.post("/api/tokens", json={"name": "t", "scopes": ["read"]})
    assert tok.status_code in (200, 201), tok.text
    secret = tok.json().get("token") or tok.json().get("secreto")
    h = {"Authorization": f"Bearer {secret}"}
    one = client.get("/api/v1/recipes/1", headers=h).json()
    assert one["source_type"] == "instagram" and one["source_url"]
    lst = client.get("/api/v1/recipes", headers=h).json()
    items = lst if isinstance(lst, list) else lst.get("recetas") or lst.get("items")
    assert all("source_url" in x and "source_type" in x for x in items)
    s = _summary(services.recipes.get(1))
    assert s["source_type"] == "instagram" and s["source_url"]


def test_exports_include_source(client):
    rid = _new(client, source_url="https://www.tiktok.com/@a/video/1")
    data = client.post("/api/export", json={"ids": [1, rid], "formato": "json"}).json()
    assert {x["source_type"] for x in data["recetas"]} == {"instagram", "tiktok"}
    leg = client.post("/api/export", json={"formato": "json_legacy"}).json()
    assert all("source_url" in x for x in leg["recetas"])
    md = client.post("/api/export", json={"ids": [rid], "formato": "markdown"}).text
    assert "[Ver original (TikTok)](https://www.tiktok.com/@a/video/1)" in md
    html = client.post("/api/export", json={"ids": [rid], "formato": "html"}).text
    assert 'href="https://www.tiktok.com/@a/video/1"' in html and 'rel="noopener noreferrer"' in html and "Ver original (TikTok)" in html
    manual = _new(client, titulo="Manual")
    md2 = client.post("/api/export", json={"ids": [manual], "formato": "markdown"}).text
    assert "Ver original" not in md2
