import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import build_services, create_app
from app.services.instagram import MockInstagramProvider

SEED = ROOT / "data" / "seed" / "recetas.json"


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    s = Settings()
    s.data_dir = tmp_path / "data"
    s.videos_dir = tmp_path / "videos"
    s.media_dir = tmp_path / "media"
    s.secret_dir = tmp_path / "secret"
    s.seed_file = SEED
    s.ig_provider = "mock"
    s.max_photo_mb = 1
    s.max_video_mb = 2
    return s


@pytest.fixture()
def services(settings):
    svc = build_services(settings, MockInstagramProvider(), import_delay=0)
    yield svc
    svc.db.close()


ADMIN = ("admin", "contraseña-de-prueba")


def login(c: TestClient, svc) -> TestClient:
    if not svc.auth.has_admin():
        svc.auth.create_admin(*ADMIN)
    r = c.post("/api/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    return c


@pytest.fixture()
def anon(services):
    with TestClient(create_app(services)) as c:
        yield c


@pytest.fixture()
def client(services):
    with TestClient(create_app(services)) as c:
        yield login(c, services)


@pytest.fixture()
def legacy() -> dict:
    return json.loads(SEED.read_text(encoding="utf-8"))


def wait_job(client, job_id, timeout=10):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = client.get(f"/api/instagram/jobs/{job_id}").json()
        if job["estado"] in ("terminado", "cancelado"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")
