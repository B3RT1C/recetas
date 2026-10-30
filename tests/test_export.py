import io
import json
import zipfile


def test_export_json_selection(client):
    r = client.post("/api/export", json={"ids": [1, 2], "formato": "json"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert [x["id"] for x in data["recetas"]] == [1, 2]


def test_export_legacy_json_roundtrip(client, legacy):
    data = client.post("/api/export", json={"formato": "json_legacy"}).json()
    assert data == legacy


def test_export_markdown_and_html(client):
    md = client.post("/api/export", json={"ids": [1], "formato": "markdown"}).text
    assert md.startswith("# Recetario C") and "## Brochetas de kebab" in md and "estimado" in md
    html = client.post("/api/export", json={"ids": [1], "formato": "html"}).text
    assert "<h2>Brochetas de kebab con tortillas</h2>" in html and "@media print" in html


def test_export_zip_with_media(client, settings):
    (settings.videos_dir / "DPpn4clj0eC.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42video")
    r = client.post("/api/export", json={"ids": [1, 2], "formato": "html", "con_media": True})
    assert r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert set(z.namelist()) == {"recetas.html", "videos/DPpn4clj0eC.mp4"}


def test_export_never_contains_secrets(client):
    client.put("/api/ai/config", json={"preset": "openai", "base_url": "https://api.openai.com/v1",
                                       "model": "gpt-4o-mini", "api_key": "sk-supersecret-1234"})
    for fmt in ("json", "json_legacy", "markdown", "html"):
        body = client.post("/api/export", json={"formato": fmt, "con_media": True}).content
        z = zipfile.ZipFile(io.BytesIO(body))
        for name in z.namelist():
            assert b"sk-supersecret" not in z.read(name)


def test_export_empty_selection(client):
    assert client.post("/api/export", json={"ids": [], "formato": "json"}).status_code == 400
