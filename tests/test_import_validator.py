"""Import validator: every code via the mock provider, batch partial failure, REST + MCP error shapes."""
import json

import anyio
import pytest

from app.services.validator import CODES, check_recipe, check_source
from test_instagram_import import login as ig_login
from conftest import wait_job
from test_tokens_and_mcp import GAZPACHO, _mcp, mk_token, server  # noqa: F401 (fixture)

KEYS = {"ok", "code", "reason_es", "reason_en", "details", "salvageable"}
IG = "https://www.instagram.com/reel/{}/"


def test_result_shape_and_recipe_checks():
    ok = check_recipe({"titulo": "x", "ingredientes": [{"nombre": "sal"}], "pasos": [{"texto": "mezcla"}]})
    assert set(ok) == KEYS and ok["ok"] and ok["code"] is None
    r = check_recipe({"titulo": "Brownie", "caption_original": "comenta BROWNIE", "ingredientes": [], "pasos": []})
    assert (r["code"], r["salvageable"]) == ("NO_INGREDIENTS", True)
    assert r["reason_es"] == "No parece una receta: no hay ingredientes." and r["reason_en"]
    assert check_recipe({"titulo": "x", "ingredientes": [{"nombre": "sal"}], "pasos": []})["code"] == "NO_STEPS"
    r = check_recipe({"titulo": "", "ingredientes": [{"nombre": "  "}], "pasos": [{"texto": ""}]})
    assert (r["code"], r["salvageable"]) == ("INSUFFICIENT_DATA", False)
    assert check_source("https://www.tiktok.com/@a/video/1")["code"] == "UNSUPPORTED_SOURCE"
    assert check_source(IG.format("ABC123"))["ok"]


@pytest.mark.parametrize("sc,code,status,salv", [
    ("NOPE404", "NOT_FOUND", 404, False),
    ("MOCKprivate", "PRIVATE", 403, False),
    ("MOCKratelim", "RATE_LIMITED", 429, False),
    ("MOCKnetwork", "NETWORK", 502, False),
    ("MOCKbrown04", "NO_INGREDIENTS", 422, True),
    ("MOCKnosteps", "NO_STEPS", 422, True),
    ("MOCKempty01", "INSUFFICIENT_DATA", 422, False),
])
def test_v1_import_each_code(client, services, sc, code, status, salv):
    rw = {"Authorization": f"Bearer {mk_token(client)['token']}"}
    before = len(services.recipes.all())
    r = client.post("/api/v1/recipes/import-url", json={"url": IG.format(sc)}, headers=rw)
    assert r.status_code == status, r.text
    err = r.json()["error"]
    assert set(err) == KEYS and err["ok"] is False and err["code"] == code and err["salvageable"] is salv
    assert err["reason_es"] and err["reason_en"] and r.json()["detail"] == err["reason_es"]
    assert len(services.recipes.all()) == before  # never an empty/broken recipe


def test_v1_unsupported_source(client):
    rw = {"Authorization": f"Bearer {mk_token(client)['token']}"}
    r = client.post("/api/v1/recipes/import-url", json={"url": "https://www.youtube.com/watch?v=x"}, headers=rw)
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNSUPPORTED_SOURCE"


def test_v1_salvageable_saved_as_draft(client):
    rw = {"Authorization": f"Bearer {mk_token(client)['token']}"}
    r = client.post("/api/v1/recipes/import-url", json={"url": IG.format("MOCKnosteps"), "guardar_borrador": True}, headers=rw)
    assert r.status_code == 422
    did = r.json()["error"]["details"]["draft_id"]
    assert any(d["id"] == did for d in client.get("/api/drafts").json())
    # an incomplete draft can't be promoted to a recipe until it's completed by hand
    r = client.post(f"/api/drafts/{did}/save")
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_STEPS"


def test_v1_create_rejects_empty_recipe(client):
    rw = {"Authorization": f"Bearer {mk_token(client)['token']}"}
    r = client.post("/api/v1/recipes", json={"titulo": "Vacía"}, headers=rw)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INSUFFICIENT_DATA"
    assert client.post("/api/v1/recipes", json=GAZPACHO, headers=rw).status_code == 201


def test_batch_continues_past_failures_with_summary(client, services):
    ig_login(client)
    items = [{"shortcode": s, "contenido": "ambos"} for s in
             ("MOCKprivate", "MOCKpasta01", "NOPE404", "MOCKbrown04", "MOCKempty01", "MOCKratelim", "MOCKflan06")]
    job = wait_job(client, client.post("/api/instagram/import", json={"items": items}).json()["id"])
    st = {i["shortcode"]: i for i in job["items"]}
    assert st["MOCKpasta01"]["estado"] == "ok" and st["MOCKflan06"]["estado"] == "ok"
    assert st["MOCKprivate"]["code"] == "PRIVATE" and st["NOPE404"]["code"] == "NOT_FOUND"
    assert st["MOCKratelim"]["code"] == "RATE_LIMITED"
    assert st["MOCKbrown04"]["estado"] == "incompleto" and st["MOCKbrown04"]["draft_id"]
    assert st["MOCKempty01"]["estado"] == "error" and st["MOCKempty01"]["draft_id"] is None
    assert job["resumen"] == {"ok": 2, "incompleto": 1, "duplicado": 0, "error": 4}
    assert {f["shortcode"]: f["code"] for f in job["fallos"]} == {
        "MOCKprivate": "PRIVATE", "NOPE404": "NOT_FOUND", "MOCKbrown04": "NO_INGREDIENTS",
        "MOCKempty01": "INSUFFICIENT_DATA", "MOCKratelim": "RATE_LIMITED"}
    assert not any(d["shortcode"] == "MOCKempty01" for d in client.get("/api/drafts").json())


def test_mcp_import_error_payload(server, services):  # noqa: F811
    rw = services.tokens.create("mcp", ["read", "write"])["token"]

    async def flow(c):
        out = {}
        for sc in ("MOCKprivate", "MOCKbrown04"):
            out[sc] = await c.call_tool("import_recipe", {"instagram_url": IG.format(sc)})
        out["tiktok"] = await c.call_tool("import_recipe", {"instagram_url": "https://www.tiktok.com/@a/video/1"})
        out["empty"] = await c.call_tool("import_recipe", {"recipe_json": json.dumps({"titulo": "Nada"})})
        return out

    before = len(services.recipes.all())
    res = anyio.run(_mcp, server, rw, flow)
    want = {"MOCKprivate": "PRIVATE", "MOCKbrown04": "NO_INGREDIENTS", "tiktok": "UNSUPPORTED_SOURCE", "empty": "INSUFFICIENT_DATA"}
    for k, code in want.items():
        assert res[k].is_error
        text = res[k].content[0].text  # SDK prefixes "Error executing tool ...: "
        payload = json.loads(text[text.index("{"):])
        assert set(payload) == KEYS and payload["code"] == code and payload["ok"] is False
    assert len(services.recipes.all()) == before


def test_all_codes_have_bilingual_reasons():
    assert set(CODES) == {"NOT_FOUND", "PRIVATE", "UNSUPPORTED_SOURCE", "NO_INGREDIENTS", "NO_STEPS",
                          "INSUFFICIENT_DATA", "RATE_LIMITED", "NETWORK"}
    assert all(es and en for es, en, _ in CODES.values())
