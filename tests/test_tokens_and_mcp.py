import json
import socket
import threading
import time

import anyio
import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.main import create_app


GAZPACHO = {"titulo": "Gazpacho MCP", "ingredientes": [{"nombre": "tomate", "cantidad_normal": "1 kg"}],
            "pasos": [{"texto": "Tritura todo."}]}


def mk_token(client, scopes=("read", "write")):
    r = client.post("/api/tokens", json={"name": "agente", "scopes": list(scopes)})
    assert r.status_code == 201
    return r.json()


def test_tokens_hashed_shown_once_and_revocable(client, settings):
    t = mk_token(client)
    assert t["token"].startswith("rct_")
    listed = client.get("/api/tokens").json()
    assert "token" not in listed[0] and t["token"] not in json.dumps(listed)
    assert t["token"].encode() not in (settings.data_dir / "recetas.db").read_bytes()
    h = {"Authorization": f"Bearer {t['token']}"}
    assert client.get("/api/v1/recipes", params={"q": "pollo", "limit": 3}, headers=h).status_code == 200
    client.delete(f"/api/tokens/{t['id']}")
    assert client.get("/api/v1/recipes", headers=h).status_code == 401


def test_v1_requires_token_and_scopes(client):
    assert client.get("/api/v1/recipes").status_code == 401
    assert client.get("/api/v1/recipes", headers={"Authorization": "Bearer rct_nope"}).status_code == 401
    ro = mk_token(client, ("read",))
    h = {"Authorization": f"Bearer {ro['token']}"}
    assert client.get("/api/v1/recipes/1", headers=h).json()["id"] == 1
    assert client.post("/api/v1/recipes", json={"titulo": "x"}, headers=h).status_code == 401
    rw = {"Authorization": f"Bearer {mk_token(client)['token']}"}
    assert client.post("/api/v1/recipes", json={**GAZPACHO, "titulo": "Desde un agente"}, headers=rw).status_code == 201
    assert "etiquetas" in client.get("/api/v1/collections", headers=rw).json()


def test_v1_import_url(client):
    rw = {"Authorization": f"Bearer {mk_token(client)['token']}"}
    url = "https://www.instagram.com/reel/MOCKtorti02/"
    assert client.post("/api/v1/recipes/import-url", json={"url": "https://example.com/x"}, headers=rw).status_code == 422
    r = client.post("/api/v1/recipes/import-url", json={"url": url}, headers=rw)
    assert r.status_code == 201 and r.json()["titulo"].startswith("Tortilla de patatas")
    assert client.post("/api/v1/recipes/import-url", json={"url": url}, headers=rw).status_code == 409


def test_openapi_docs(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/recipes" in paths and "/api/v1/recipes/import-url" in paths


# ---------------------------------------------------------------- MCP over real HTTP
@pytest.fixture()
def server(services):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    services.settings.host = "127.0.0.1"
    cfg = uvicorn.Config(create_app(services), host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(cfg)
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    th.join(5)


async def _mcp(url: str, token: str, fn):
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=10) as http:
        async with Client(streamable_http_client(f"{url}/mcp/", http_client=http)) as c:
            return await fn(c)


def _payload(result):
    if getattr(result, "structured_content", None) is not None:
        sc = result.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    return json.loads(result.content[0].text)


def test_mcp_rejects_without_token(server):
    r = httpx2.post(f"{server}/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401


def test_mcp_tools_with_sdk_client(server, services):
    rw = services.tokens.create("mcp", ["read", "write"])["token"]
    ro = services.tokens.create("mcp-ro", ["read"])["token"]

    async def flow(c):
        names = {t.name for t in (await c.list_tools()).tools}
        assert {"search_recipes", "get_recipe", "list_collections", "import_recipe"} <= names
        found = _payload(await c.call_tool("search_recipes", {"query": "kebab", "limit": 5}))
        assert found and found[0]["id"] == 1
        rec = _payload(await c.call_tool("get_recipe", {"recipe_id": 1}))
        assert rec["titulo"] == "Brochetas de kebab con tortillas"
        cols = _payload(await c.call_tool("list_collections", {}))
        assert cols["tipos"]["solo_video"] == 73
        new = _payload(await c.call_tool("import_recipe", {"recipe_json": json.dumps(GAZPACHO)}))
        return new

    new = anyio.run(_mcp, server, rw, flow)
    assert new["titulo"] == "Gazpacho MCP" and services.recipes.get(new["id"])

    async def ro_flow(c):
        res = await c.call_tool("import_recipe", {"recipe_json": json.dumps({"titulo": "No"})})
        return res

    res = anyio.run(_mcp, server, ro, ro_flow)
    assert res.is_error and "write" in res.content[0].text
