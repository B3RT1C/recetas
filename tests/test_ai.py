import logging

import httpx

from app.services.ai import FakeAIProvider, OpenAICompatibleProvider

KEY = "sk-test-abcdefgh9876"


def configure(client, key=KEY):
    return client.put("/api/ai/config", json={"preset": "openrouter", "base_url": "https://openrouter.ai/api/v1/",
                                              "model": "openai/gpt-4o-mini", "api_key": key})


def test_key_is_masked_encrypted_and_kept(client, settings, services):
    cfg = configure(client).json()
    assert cfg["api_key_hint"] == "••••9876" and KEY not in str(cfg) and cfg["base_url"] == "https://openrouter.ai/api/v1"
    assert KEY not in client.get("/api/ai/config").text
    raw = (settings.data_dir / "recetas.db").read_bytes()
    assert KEY.encode() not in raw  # encrypted at rest
    assert (settings.secret_dir / "secret.key").exists() and not (settings.data_dir / "secret.key").exists()
    # updating without api_key keeps the stored one
    client.put("/api/ai/config", json={"preset": "openrouter", "base_url": "https://openrouter.ai/api/v1", "model": "x"})
    assert client.get("/api/ai/config").json()["api_key_hint"] == "••••9876"
    assert services.ai.provider()._api_key == KEY
    client.put("/api/ai/config", json={"preset": "ollama", "base_url": "http://localhost:11434/v1", "model": "llama3.1", "api_key": ""})
    assert client.get("/api/ai/config").json()["tiene_api_key"] is False


def test_test_connection(client, services):
    assert client.post("/api/ai/test").json()["ok"] is False
    services.ai.override = FakeAIProvider()
    assert client.post("/api/ai/test").json() == {"ok": True, "respuesta": "ok"}
    services.ai.override = FakeAIProvider(fail=True)
    assert client.post("/api/ai/test").json()["ok"] is False


def test_openai_compatible_provider_wire_format(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, body=json, headers=headers)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    p = OpenAICompatibleProvider("http://localhost:1234/v1/", "m", KEY)
    assert p.ping()["ok"]
    assert seen["url"] == "http://localhost:1234/v1/chat/completions" and seen["headers"]["Authorization"] == f"Bearer {KEY}"
    assert KEY not in caplog.text

    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(401, json={"error": KEY}))
    try:
        p.ping()
    except Exception as e:  # noqa: BLE001
        assert KEY not in str(e) and "401" in str(e)


def test_translate_and_estimate(client, services):
    assert client.post("/api/ai/translate", json={"recipe_id": 1, "lang": "en"}).status_code == 502
    services.ai.override = FakeAIProvider()
    t = client.post("/api/ai/translate", json={"recipe_id": 1, "lang": "en"}).json()
    assert t["titulo"].startswith("[en] ") and len(t["ingredientes"]) == len(client.get("/api/recipes/1").json()["ingredientes"])
    e = client.post("/api/ai/estimate", json={"recipe": {"titulo": "x", "ingredientes": [{"nombre": "sal", "unidad": "ud"}]}}).json()
    assert e["ingredientes"][0]["precio_eur"] == 0.5 and e["ingredientes"][0]["estimada"] is True and e["precios_estimados_ia"]
    # the original recipe is not modified until the user saves
    assert not client.get("/api/recipes/1").json()["titulo"].startswith("[en]")
