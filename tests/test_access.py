import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import access as A
from app.config import parse_dotenv, load_dotenv


# ------------------------------------------------------------- validation
def _v(host, port, cur=8088, bind=lambda h, p: True, ips=lambda: ["127.0.0.1", "192.168.1.20", "100.101.2.3"]):
    return A.validate(host, port, "0.0.0.0", cur, bind=bind, ips=ips)


@pytest.mark.parametrize("port", [0, 80, 1023, 65536, "abc", "", None, 8088.5])
def test_bad_ports(port):
    with pytest.raises(A.ConfigError):
        _v("0.0.0.0", port)


@pytest.mark.parametrize("host", ["", "localhost", "10.9.9.9", "::1", "1.2.3", "0.0.0.0; rm"])
def test_bad_hosts(host):
    with pytest.raises(A.ConfigError):
        _v(host, 9000)


def test_good_values():
    assert _v("0.0.0.0", "9000") == ("0.0.0.0", 9000)
    assert _v("127.0.0.1", 1024) == ("127.0.0.1", 1024)
    assert _v("192.168.1.20", 65535) == ("192.168.1.20", 65535)


def test_port_in_use_but_current_is_free():
    busy = lambda h, p: False
    with pytest.raises(A.ConfigError, match="en uso"):
        _v("0.0.0.0", 9000, bind=busy)
    assert _v("0.0.0.0", 8088, bind=busy) == ("0.0.0.0", 8088)


def test_can_bind_detects_real_listener():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen()
    try:
        assert not A.can_bind("127.0.0.1", s.getsockname()[1])
    finally:
        s.close()


# ------------------------------------------------------------- config file
def test_atomic_write_keeps_other_keys(tmp_path, monkeypatch):
    f = tmp_path / "config.env"
    f.write_text("# comentario\nRECETAS_VIDEOS_DIR=D:\\v\nRECETAS_PORT=8088\n", encoding="utf-8")
    A.write_config(f, {"RECETAS_HOST": "127.0.0.1", "RECETAS_PORT": "9001"})
    txt = f.read_text(encoding="utf-8")
    assert txt.splitlines() == ["# comentario", "RECETAS_VIDEOS_DIR=D:\\v", "RECETAS_PORT=9001", "RECETAS_HOST=127.0.0.1"]
    assert list(tmp_path.iterdir()) == [f]  # no temp leftovers

    def boom(*a):
        raise OSError("disk full")
    monkeypatch.setattr(A.os, "replace", boom)
    with pytest.raises(OSError):
        A.write_config(f, {"RECETAS_PORT": "1"})
    assert f.read_text(encoding="utf-8") == txt and list(tmp_path.iterdir()) == [f]


def test_dotenv_parser_and_precedence(tmp_path, monkeypatch):
    f = tmp_path / "x.env"
    f.write_text('\ufeff# c\nexport RECETAS_PORT="9100"\nRECETAS_HOST=127.0.0.1 # local\nBAD LINE\nRECETAS_FFMPEG=\'C:\\f f\\ffmpeg.exe\'\n',
                 encoding="utf-8")
    assert parse_dotenv(f.read_text(encoding="utf-8-sig")) == {
        "RECETAS_PORT": "9100", "RECETAS_HOST": "127.0.0.1", "RECETAS_FFMPEG": "C:\\f f\\ffmpeg.exe"}
    monkeypatch.setenv("RECETAS_HOST", "0.0.0.0")  # real env beats the file
    for k in ("RECETAS_PORT", "RECETAS_FFMPEG"):  # setenv first so monkeypatch restores whatever load_dotenv adds
        monkeypatch.setenv(k, "x")
        monkeypatch.delenv(k)
    monkeypatch.setenv("RECETAS_CONFIG_FILE", str(f))
    applied = load_dotenv()
    import os
    assert os.environ["RECETAS_HOST"] == "0.0.0.0" and os.environ["RECETAS_PORT"] == "9100"
    assert "RECETAS_HOST" not in applied
    from app.config import Settings
    assert Settings().port == 9100


def test_cli_beats_env(monkeypatch, tmp_path):
    for k in ("RECETAS_DATA_DIR", "RECETAS_MEDIA_DIR", "RECETAS_SECRET_DIR", "RECETAS_VIDEOS_DIR"):
        monkeypatch.setenv(k, str(tmp_path / k.lower()))
    monkeypatch.setenv("RECETAS_SEED_FILE", str(tmp_path / "none.json"))
    import run, sys
    f = tmp_path / "c.env"; f.write_text("RECETAS_PORT=9100\n", encoding="utf-8")
    monkeypatch.setenv("RECETAS_CONFIG_FILE", str(f))
    monkeypatch.setenv("RECETAS_PORT", "9200")
    seen = {}
    import uvicorn
    monkeypatch.setattr(uvicorn, "run", lambda app, host, port, **k: seen.update(host=host, port=port))
    monkeypatch.setattr(sys, "argv", ["run.py", "--port", "9300", "--mock-instagram"])
    run.main()
    assert seen["port"] == 9300
    monkeypatch.setenv("RECETAS_PORT", "9200")  # run.main exports the CLI value
    monkeypatch.setattr(sys, "argv", ["run.py", "--mock-instagram"])
    run.main()
    assert seen["port"] == 9200


# ------------------------------------------------------------- API
class FakeOps(A.SystemOps):
    def __init__(self, cfg):
        self.config_file, self.enabled, self.calls = cfg, True, []

    def add_firewall(self, port):
        self.calls.append(("add", port)); return True

    def remove_firewall(self, port):
        self.calls.append(("remove", port)); return True

    def restart(self):
        self.calls.append(("restart",)); return True


def _logged(app):
    c = TestClient(app)
    c.__enter__()
    csrf = c.post("/api/auth/setup", json={"username": "admin", "password": "una-clave-larga-1"}).json()["csrf"]
    return c, csrf


@pytest.fixture
def app_ops(tmp_path, monkeypatch):
    for k in ("RECETAS_DATA_DIR", "RECETAS_MEDIA_DIR", "RECETAS_SECRET_DIR", "RECETAS_VIDEOS_DIR"):
        monkeypatch.setenv(k, str(tmp_path / k.lower()))
    monkeypatch.setenv("RECETAS_IG_PROVIDER", "mock")
    monkeypatch.setenv("RECETAS_SEED_FILE", str(tmp_path / "none.json"))
    monkeypatch.setenv("RECETAS_PORT", "8088")
    monkeypatch.setattr(A, "local_ips", lambda: ["127.0.0.1", "192.168.1.20"])
    monkeypatch.setattr(A, "can_bind", lambda h, p: p != 9999)
    from app.main import create_app
    app = create_app()
    cfg = tmp_path / "config.env"
    cfg.write_text("RECETAS_HOST=0.0.0.0\nRECETAS_PORT=8088\nOTRA=1\n", encoding="utf-8")
    ops = FakeOps(cfg)
    app.state.access_ops = ops
    c, csrf = _logged(app)
    yield app, c, csrf, ops, cfg
    c.__exit__(None, None, None)


def test_access_requires_login_and_csrf(app_ops):
    app, c, csrf, ops, cfg = app_ops
    anon = TestClient(app)
    assert anon.get("/api/acceso").status_code == 401
    assert anon.put("/api/acceso/red", json={"host": "0.0.0.0", "port": 9000}).status_code == 401
    assert c.put("/api/acceso/red", json={"host": "0.0.0.0", "port": 9000}).status_code == 403  # no CSRF header
    assert c.put("/api/acceso/red", json={"host": "0.0.0.0", "port": 9000},
                 headers={"X-CSRF-Token": csrf, "Origin": "http://evil.example"}).status_code == 403
    assert ops.calls == [] and "9000" not in cfg.read_text()


def test_access_get_and_qr(app_ops):
    app, c, csrf, ops, cfg = app_ops
    a = c.get("/api/acceso").json()
    assert a["port"] == 8088 and any(u["url"] == "http://192.168.1.20:8088/" for u in a["urls"])
    r = c.get("/api/acceso/qr", params={"url": "http://192.168.1.20:8088/"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and "<path" in r.text
    assert c.get("/api/acceso/qr", params={"url": "http://evil/"}).status_code == 400


def test_access_change_port_flow(app_ops, tmp_path):
    app, c, csrf, ops, cfg = app_ops
    h = {"X-CSRF-Token": csrf}
    assert c.put("/api/acceso/red", json={"host": "0.0.0.0", "port": 9999}, headers=h).status_code == 422
    assert c.put("/api/acceso/red", json={"host": "8.8.8.8", "port": 9000}, headers=h).status_code == 422
    assert ops.calls == []
    r = c.put("/api/acceso/red", json={"host": "0.0.0.0", "port": 9000}, headers=h)
    assert r.status_code == 200 and r.json()["reiniciando"] is True
    assert ops.calls == [("add", 9000), ("restart",)]  # old rules stay until the new port is healthy
    assert cfg.read_text().splitlines() == ["RECETAS_HOST=0.0.0.0", "RECETAS_PORT=9000", "OTRA=1"]
    # the "new" server comes up on 9000: first health check removes the old port's rules
    assert A.cleanup_old_rules(ops, tmp_path / "recetas_secret_dir", 9000) == 8088
    assert ops.calls[-1] == ("remove", 8088)


def test_rollback_drops_new_rules(tmp_path):
    ops = FakeOps(None)
    A.pending_cleanup_file(tmp_path).write_text("8088,9000", encoding="utf-8")
    assert A.cleanup_old_rules(ops, tmp_path, 8088) == 9000
    assert not A.pending_cleanup_file(tmp_path).exists()


def test_same_port_host_change_restarts_without_firewall(app_ops):
    app, c, csrf, ops, cfg = app_ops
    r = c.put("/api/acceso/red", json={"host": "127.0.0.1", "port": 8088}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200 and ops.calls == [("restart",)]


def test_noop_off_windows(app_ops, monkeypatch):
    app, c, csrf, ops, cfg = app_ops
    monkeypatch.setattr(A.sys, "platform", "linux")
    real = A.SystemOps(cfg)
    assert not real.enabled and "Windows" in real.unavailable_reason()
    monkeypatch.setattr(A.sys, "platform", "win32")
    assert "RECETAS_CONFIG_FILE" in A.SystemOps(None).unavailable_reason()
    monkeypatch.setattr(A.sys, "platform", "linux")
    app.state.access_ops = real
    r = c.put("/api/acceso/red", json={"host": "0.0.0.0", "port": 9001}, headers={"X-CSRF-Token": csrf}).json()
    assert r["reiniciando"] is False and "a mano" in r["mensajes"][0] and "RECETAS_PORT=9001" in cfg.read_text()


def test_firewall_commands_only_touch_own_rules(monkeypatch):
    calls = []
    ops = A.SystemOps(Path("x"))
    monkeypatch.setattr(ops, "_run", lambda args: calls.append(args) or True)
    ops.add_firewall(9000); ops.remove_firewall(8088); ops.restart()
    names = [a for args in calls for a in args if a.startswith("name=")]
    assert names == ["name=Recetario 9000 (LAN)", "name=Recetario 9000 (Tailscale)",
                     "name=Recetario 8088 (LAN)", "name=Recetario 8088 (Tailscale)"]
    assert "remoteip=100.64.0.0/10" in calls[1] and "profile=private" in calls[0]
    assert calls[-1] == ["schtasks", "/Run", "/TN", "RecetasWeb"]
