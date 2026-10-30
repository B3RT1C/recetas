import shutil
import subprocess

import pytest

from app.services.thumbs import ThumbService

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def make_video(path):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=orange:s=320x568:d=2", "-pix_fmt", "yuv420p", str(path)], check=True)


def first_with_shortcode(client):
    return next(r for r in client.get("/api/recipes").json() if r["shortcode"])


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_cover_from_local_video(client, services, settings):
    r = first_with_shortcode(client)
    assert r["portada"] is None                       # nothing local yet -> UI shows emoji
    make_video(settings.videos_dir / f"{r['shortcode']}.mp4")
    services.thumbs.autostart = False
    r = client.get(f"/api/recipes/{r['id']}").json()  # queues the job, falls back meanwhile
    assert r["portada"] is None and services.thumbs.q.qsize() == 1
    services.thumbs.drain()
    r = client.get(f"/api/recipes/{r['id']}").json()
    assert r["portada"].startswith(f"/media/thumbs/{r['shortcode']}.jpg")
    img = client.get(r["portada"])
    assert img.status_code == 200 and img.content[:3] == b"\xff\xd8\xff"


def test_cover_falls_back_to_imported_photo(client, settings):
    r = first_with_shortcode(client)
    (settings.media_dir / "photos").mkdir(parents=True, exist_ok=True)
    (settings.media_dir / "photos" / f"{r['shortcode']}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    assert client.get(f"/api/recipes/{r['id']}").json()["portada"] == f"/media/photos/{r['shortcode']}.jpg"


def test_missing_ffmpeg_is_graceful(client, services, settings):
    settings.ffmpeg = "/nonexistent/ffmpeg.exe"
    r = first_with_shortcode(client)
    (settings.videos_dir / f"{r['shortcode']}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    assert client.get(f"/api/recipes/{r['id']}").json()["portada"] is None
    st = client.get("/api/estado").json()["cola"]["portadas"]
    assert st["disponible"] is False and st["ffmpeg"] is None


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_broken_video_is_recorded_not_retried(settings, tmp_path):
    t = ThumbService(settings, autostart=False)
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    assert t.enqueue("BAD", bad)
    t.drain()
    assert "BAD" in t.failed and not t.enqueue("BAD", bad)
    assert t.status()["fallidas"] == 1


def test_estado_panel(client, settings):
    settings.ffmpeg = ""
    r = first_with_shortcode(client)
    (settings.videos_dir / f"{r['shortcode']}.mp4").write_bytes(b"x" * 1000)
    e = client.get("/api/estado?refrescar=true").json()
    assert e["version"] and e["esquema"] == e["esquema_ultimo"]
    assert e["disco"]["videos"]["bytes"] == 1000 and e["disco"]["libre_bytes"] > 0
    v = e["videos"]
    assert v["con_video_local"] == 1 and v["sin_video"] == v["recetas_con_publicacion"] - 1
    assert "importaciones" in e and "portadas" in e["cola"]


def test_estado_lists_finished_imports(client):
    from tests.conftest import wait_job
    job = client.post("/api/instagram/import", json={"items": [{"shortcode": "MOCKflan06", "contenido": "foto"}]}).json()
    wait_job(client, job["id"])
    e = client.get("/api/estado").json()
    assert e["importaciones"][0]["id"] == job["id"] and e["importaciones"][0]["total"] == 1
