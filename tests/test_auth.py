import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.cli import main as cli_main
from app.services.auth import AuthError, AuthService
from tests.conftest import ADMIN, login


def test_ui_api_requires_session_but_open_routes_dont(anon, services):
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/").status_code == 200
    assert anon.get("/assets/app.js").status_code == 200
    for path in ("/api/recipes", "/api/meta", "/api/tokens", "/media/x.jpg", "/videos/x.mp4", "/openapi.json"):
        assert anon.get(path).status_code == 401, path
    assert anon.get("/api/auth/me").json() == {"autenticado": False, "necesita_configuracion": True}
    # /api/v1 keeps bearer auth (401 without token, works with token)
    assert anon.get("/api/v1/recipes").status_code == 401
    tok = services.tokens.create("t", ["read"])["token"]
    assert anon.get("/api/v1/recipes", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_login_cookie_flags_and_csrf(anon, services):
    services.auth.create_admin(*ADMIN)
    r = anon.post("/api/auth/login", json={"username": "admin", "password": ADMIN[1]})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" not in cookie
    csrf = r.json()["csrf"]
    assert anon.get("/api/recipes").status_code == 200
    # state-changing without / with wrong CSRF header -> 403
    assert anon.post("/api/tokens", json={"name": "x", "scopes": ["read"]}).status_code == 403
    assert anon.post("/api/tokens", json={"name": "x", "scopes": ["read"]},
                     headers={"X-CSRF-Token": "nope"}).status_code == 403
    assert anon.post("/api/tokens", json={"name": "x", "scopes": ["read"]},
                     headers={"X-CSRF-Token": csrf, "Origin": "http://evil.example"}).status_code == 403
    assert anon.post("/api/tokens", json={"name": "x", "scopes": ["read"]},
                     headers={"X-CSRF-Token": csrf}).status_code == 201
    anon.post("/api/auth/logout")
    assert anon.get("/api/recipes").status_code == 401


def test_secure_cookie_behind_https_proxy(anon, services):
    services.auth.create_admin(*ADMIN)
    r = anon.post("/api/auth/login", json={"username": "admin", "password": ADMIN[1]},
                  headers={"X-Forwarded-Proto": "https"})
    assert "secure" in r.headers["set-cookie"].lower()


def test_first_run_setup(anon, services):
    r = anon.post("/api/auth/setup", json={"username": "chef", "password": "corta"})
    assert r.status_code == 422
    r = anon.post("/api/auth/setup", json={"username": "chef", "password": "una-buena-clave"})
    assert r.status_code == 200 and r.json()["usuario"] == "chef"
    assert anon.get("/api/recipes").status_code == 200
    assert anon.post("/api/auth/setup", json={"username": "x", "password": "otra-buena-clave"}).status_code == 409


def test_password_is_hashed(services):
    services.auth.create_admin("admin", ADMIN[1])
    h = services.db.query("SELECT pw_hash FROM users")[0]["pw_hash"]
    assert h.startswith("$argon2") and ADMIN[1] not in h


def test_bruteforce_lockout_with_backoff(services):
    t = [1000.0]
    a = AuthService(services.db, clock=lambda: t[0])
    a.create_admin(*ADMIN)
    for _ in range(5):
        with pytest.raises(AuthError) as e:
            a.login("admin", "mala", "1.2.3.4")
        assert e.value.retry_after == 0
    with pytest.raises(AuthError) as e:  # locked now, even with the right password
        a.login("admin", ADMIN[1], "1.2.3.4")
    assert e.value.retry_after == 30
    # per account: another IP is also locked for this username
    with pytest.raises(AuthError):
        a.login("admin", ADMIN[1], "5.6.7.8")
    t[0] += 31
    with pytest.raises(AuthError):
        a.login("admin", "mala", "1.2.3.4")   # 6th failure -> 60 s lock
    t[0] += 1
    with pytest.raises(AuthError) as e:
        a.login("admin", ADMIN[1], "1.2.3.4")
    assert 55 <= e.value.retry_after <= 60
    t[0] += 61
    a.login("admin", ADMIN[1], "1.2.3.4")   # success resets the counter
    with pytest.raises(AuthError) as e:
        a.login("admin", "mala", "1.2.3.4")
    assert e.value.retry_after == 0


def test_login_429_over_http(anon, services):
    services.auth.create_admin(*ADMIN)
    for _ in range(5):
        assert anon.post("/api/auth/login", json={"username": "admin", "password": "x"}).status_code == 401
    r = anon.post("/api/auth/login", json={"username": "admin", "password": ADMIN[1]})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_cli_create_admin(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RECETAS_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("RECETAS_SECRET_DIR", str(tmp_path / "s"))
    monkeypatch.setenv("RECETAS_VIDEOS_DIR", str(tmp_path / "v"))
    monkeypatch.setenv("RECETAS_MEDIA_DIR", str(tmp_path / "m"))
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("clave-secreta-larga\n"))
    assert cli_main(["create-admin", "--username", "chef", "--password-stdin"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO("clave-secreta-larga\n"))
    assert cli_main(["create-admin", "--username", "otro", "--password-stdin"]) == 1
    from app.db import Database
    db = Database(tmp_path / "d" / "recetas.db")
    assert db.query("SELECT username FROM users")[0]["username"] == "chef"


def test_setup_behind_proxy_needs_code(anon, services):
    """A reverse proxy on the same host makes every client look local: then the setup code is required."""
    h = {"X-Forwarded-For": "203.0.113.9"}
    r = anon.post("/api/auth/setup", json={"username": "chef", "password": "una-buena-clave"}, headers=h)
    assert r.status_code == 403 and not services.auth.has_admin()
    code = (services.settings.secret_dir / "setup-code.txt").read_text().strip()
    r = anon.post("/api/auth/setup", json={"username": "chef", "password": "una-buena-clave", "code": code}, headers=h)
    assert r.status_code == 200


def _build_static(out):
    """Run the static build in a subprocess; show its output if it fails (Windows CI debugging)."""
    import os, subprocess, sys
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    p = subprocess.run([sys.executable, "scripts/build_static.py", "--out", str(out)],
                       cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    assert p.returncode == 0, f"build_static exit {p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"


def test_static_build_bypasses_login(tmp_path):
    import subprocess, sys, json
    out = tmp_path / "dist"
    _build_static(out)
    data = json.loads((out / "data" / "recipes.json").read_text(encoding="utf-8"))
    assert data["recetas"] and all(r["portada"] is None or r["portada"].startswith("media/covers/") for r in data["recetas"])
    assert 'data-mode="static"' in (out / "index.html").read_text(encoding="utf-8")


def test_static_demo_uses_only_sample_data(tmp_path):
    import subprocess, sys, json
    out = tmp_path / "dist"
    _build_static(out)
    raw = (out / "data" / "recipes.json").read_text(encoding="utf-8")
    assert "instagram.com" not in raw and "@" not in raw
    assert len(json.loads(raw)["recetas"]) == 12
