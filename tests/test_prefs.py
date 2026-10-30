def test_prefs_require_login(anon):
    assert anon.get("/api/preferencias/lista").status_code == 401
    assert anon.put("/api/preferencias/lista", json={"vista": "una"}).status_code == 401


def test_prefs_default_and_roundtrip(client):
    assert client.get("/api/preferencias/lista").json() == {"vista": "cuadricula", "densidad": 4}
    r = client.put("/api/preferencias/lista", json={"vista": "detalle", "densidad": 6})
    assert r.status_code == 200 and r.json() == {"vista": "detalle", "densidad": 6}
    assert client.get("/api/preferencias/lista").json() == {"vista": "detalle", "densidad": 6}


def test_prefs_validation(client):
    for body in ({"vista": "mosaico"}, {"vista": "una", "densidad": 1}, {"vista": "una", "densidad": 9}, {}):
        assert client.put("/api/preferencias/lista", json=body).status_code == 422
    assert client.get("/api/preferencias/lista").json()["vista"] == "cuadricula"


def test_prefs_csrf(client):
    tok = client.headers.pop("X-CSRF-Token")
    assert client.put("/api/preferencias/lista", json={"vista": "una"}).status_code == 403
    client.headers["X-CSRF-Token"] = tok


def test_prefs_ignore_corrupt_stored_value(client, services):
    services.db.set_setting("prefs:admin:lista", {"vista": "rara", "densidad": 99})
    assert client.get("/api/preferencias/lista").json() == {"vista": "cuadricula", "densidad": 4}
