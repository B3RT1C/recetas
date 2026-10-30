"""v2.1.2 covers: original thumbnail first, black-frame skip, picker API, reimport never overwrites."""
import shutil
import struct
import subprocess

import pytest

from app.services import imgmeta
from app.services.thumbs import BLACK_LUMA, ThumbService
from tests.conftest import wait_job

HAS_FFMPEG = shutil.which("ffmpeg") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")


def synthetic_video(path, black_s=2.5, total_s=5):
    """Synthetic test clip (tests only): black for ``black_s`` seconds, then bright orange. 9:16."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c=black:s=180x320:d={black_s}:r=10",
                    "-f", "lavfi", "-i", f"color=c=orange:s=180x320:d={total_s - black_s}:r=10",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]", "-pix_fmt", "yuv420p",
                    str(path)], check=True)


def first_with_shortcode(client):
    return next(r for r in client.get("/api/recipes").json() if r["shortcode"])


@needs_ffmpeg
def test_auto_frame_skips_black_frames(settings, tmp_path):
    video = tmp_path / "v.mp4"
    synthetic_video(video)
    th = ThumbService(settings, autostart=False)
    assert th.extract("k", video)
    y = th.luma(th.path_for("k"))
    assert y is not None and y >= BLACK_LUMA          # 1 s and 2 s were black -> 3 s (orange) used


@needs_ffmpeg
def test_all_black_video_keeps_least_dark_frame(settings, tmp_path):
    video = tmp_path / "b.mp4"
    synthetic_video(video, black_s=4.5, total_s=5)      # bright only after the last auto timestamp < 5
    th = ThumbService(settings, autostart=False)
    assert th.extract("b", video, times=(1.0, 2.0))
    assert th.path_for("b").exists() and "b" not in th.failed


def test_original_thumbnail_wins_over_video_frame(client, services, settings):
    r = first_with_shortcode(client)
    sc = r["shortcode"]
    (settings.videos_dir).mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / f"{sc}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    (settings.media_dir / "originals").mkdir(parents=True, exist_ok=True)
    (settings.media_dir / "originals" / f"{sc}.jpg").write_bytes(b"\xff\xd8\xff\xe0x")
    services.recipes.refresh_import_media(r["id"], {"miniatura": f"media/originals/{sc}.jpg"})
    got = client.get(f"/api/recipes/{r['id']}").json()
    assert got["portada"] == f"/media/originals/{sc}.jpg" and got["portada_efectiva"] == "original"
    assert got["portada_fuente"] is None


def test_video_only_import_keeps_original_thumbnail(client):
    job = client.post("/api/instagram/import", json={"items": [{"shortcode": "MOCKpasta01", "contenido": "video"}]}).json()
    wait_job(client, job["id"])
    draft = next(x for x in client.get("/api/drafts").json() if x["shortcode"] == "MOCKpasta01")
    assert draft["miniatura"] == "media/originals/MOCKpasta01.jpg" and "foto" not in draft
    rec = client.post(f"/api/drafts/{draft['id']}/save")
    assert rec.status_code == 201, rec.text
    rec = rec.json()
    assert rec["portada"] == "/media/originals/MOCKpasta01.jpg" and rec["portada_efectiva"] == "original"


def test_generic_cover_and_library(client):
    lib = client.get("/api/portadas/biblioteca").json()
    assert len(lib) >= 12 and all(x["credito"] for x in lib)
    rid = first_with_shortcode(client)["id"]
    r = client.put(f"/api/recipes/{rid}/portada", json={"fuente": "generic", "biblioteca": "paella"}).json()
    assert r["portada"] == "/media/library/paella.jpg" and r["portada_fuente"] == "generic"
    assert client.get(r["portada"]).status_code == 200
    assert client.put(f"/api/recipes/{rid}/portada", json={"fuente": "generic", "biblioteca": "nope"}).status_code == 422
    r = client.put(f"/api/recipes/{rid}/portada", json={"fuente": None}).json()
    assert r["portada_fuente"] is None


def _jpeg_with_exif() -> bytes:
    tiff = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 1) + \
        struct.pack("<HHII", 0x0112, 3, 1, 1) + b"\x00\x00\x00\x00"   # orientation=1
    app1 = b"Exif\x00\x00" + tiff + b"GPSsecret"
    seg = b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1
    body = b"\xff\xdb" + struct.pack(">H", 3) + b"\x00" + b"\xff\xda" + struct.pack(">H", 2) + b"\x11\x22" + b"\xff\xd9"
    return b"\xff\xd8" + seg + body


def test_strip_metadata():
    raw = _jpeg_with_exif()
    clean = imgmeta.strip(raw, "jpg")
    assert b"Exif" not in clean and b"GPSsecret" not in clean and clean.endswith(b"\xff\xd9")
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 4) + b"tEXtabcd" + b"\x00" * 4 + struct.pack(">I", 0) + b"IEND" + b"\x00" * 4
    assert b"tEXt" not in imgmeta.strip(png, "png")


def test_upload_cover_validates_and_strips(client, settings):
    rid = first_with_shortcode(client)["id"]
    bad = client.post(f"/api/recipes/{rid}/portada/subir", files={"file": ("x.gif", b"GIF89a....", "image/gif")})
    assert bad.status_code == 415
    big = client.post(f"/api/recipes/{rid}/portada/subir",
                      files={"file": ("x.jpg", b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024), "image/jpeg")})
    assert big.status_code == 413
    r = client.post(f"/api/recipes/{rid}/portada/subir", files={"file": ("x.jpg", _jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["portada_fuente"] == "upload" and r["portada"].startswith(f"/media/recipes/{rid}/portada.")
    stored = (settings.media_dir / "recipes" / str(rid)).glob("portada.*").__next__().read_bytes()
    assert b"Exif" not in stored and b"GPSsecret" not in stored


@pytest.mark.parametrize("fuente", ["upload", "generic", "frame"])
def test_reimport_never_overwrites_manual_cover(client, services, settings, fuente):
    if fuente == "frame" and not HAS_FFMPEG:
        pytest.skip("ffmpeg not installed")
    job = client.post("/api/instagram/import", json={"items": [{"shortcode": "MOCKflan06", "contenido": "foto"}]}).json()
    wait_job(client, job["id"])
    draft = next(d for d in client.get("/api/drafts").json() if d["shortcode"] == "MOCKflan06")
    rid = client.post(f"/api/drafts/{draft['id']}/save").json()["id"]
    if fuente == "upload":
        client.post(f"/api/recipes/{rid}/portada/subir", files={"file": ("x.jpg", _jpeg_with_exif(), "image/jpeg")})
    elif fuente == "generic":
        client.put(f"/api/recipes/{rid}/portada", json={"fuente": "generic", "biblioteca": "flan-de-huevo"})
    else:
        synthetic_video(settings.videos_dir / "MOCKflan06.mp4")
        services.recipes.refresh_import_media(rid, {"video": "videos/MOCKflan06.mp4"})
        r = client.put(f"/api/recipes/{rid}/portada", json={"fuente": "frame", "segundo": 3.5})
        assert r.status_code == 200, r.text
    before = client.get(f"/api/recipes/{rid}").json()
    assert before["portada_fuente"] == fuente and before["portada_efectiva"] == fuente
    job = client.post("/api/instagram/import", json={"items": [
        {"shortcode": "MOCKflan06", "contenido": "foto", "reimportar": True}]}).json()
    done = wait_job(client, job["id"])
    assert done["items"][0]["estado"] == "ok", done
    after = client.get(f"/api/recipes/{rid}").json()
    assert after["reimportado"]
    assert (after["portada_fuente"], after["portada_param"], after["portada"]) == \
        (before["portada_fuente"], before["portada_param"], before["portada"])


def test_reimport_original_cover_follows_new_thumbnail(client):
    job = client.post("/api/instagram/import", json={"items": [{"shortcode": "MOCKflan06", "contenido": "video"}]}).json()
    wait_job(client, job["id"])
    draft = next(d for d in client.get("/api/drafts").json() if d["shortcode"] == "MOCKflan06")
    rid = client.post(f"/api/drafts/{draft['id']}/save").json()["id"]
    job = client.post("/api/instagram/import", json={"items": [
        {"shortcode": "MOCKflan06", "contenido": "foto", "reimportar": True}]}).json()
    wait_job(client, job["id"])
    r = client.get(f"/api/recipes/{rid}").json()
    assert r["portada_efectiva"] == "original" and r["portada"] == "/media/photos/MOCKflan06.png"


@needs_ffmpeg
def test_frame_preview_and_choice(client, services, settings):
    r = first_with_shortcode(client)
    synthetic_video(settings.videos_dir / f"{r['shortcode']}.mp4")
    p = client.get(f"/api/recipes/{r['id']}/portada/fotograma", params={"t": 0.5})
    assert p.status_code == 200 and p.content[:3] == b"\xff\xd8\xff" and p.headers["x-fotograma-negro"] == "1"
    p = client.get(f"/api/recipes/{r['id']}/portada/fotograma", params={"t": 4})
    assert p.headers["x-fotograma-negro"] == "0"
    got = client.put(f"/api/recipes/{r['id']}/portada", json={"fuente": "frame", "segundo": 4}).json()
    assert got["portada_efectiva"] == "frame" and "__t4000.jpg" in got["portada"]
    # editing the recipe never touches the cover choice
    client.put(f"/api/recipes/{r['id']}", json={**got, "titulo": got["titulo"] + " (ed.)"})
    assert client.get(f"/api/recipes/{r['id']}").json()["portada_param"] == "4"


def test_global_default_setting(client):
    assert client.get("/api/ajustes/portada").json()["predeterminada"] == "original"
    assert client.put("/api/ajustes/portada", json={"predeterminada": "generic"}).status_code == 200
    r = next(x for x in client.get("/api/recipes").json() if x["tipo"] == "receta")
    assert r["portada_efectiva"] == "generic" and r["portada"].startswith("/media/library/")
    assert client.put("/api/ajustes/portada", json={"predeterminada": "upload"}).status_code == 422


def test_migration_adds_cover_columns(services):
    cols = {r[1] for r in services.db.conn.execute("PRAGMA table_info(recipes)")}
    assert {"cover_source", "cover_param"} <= cols


def test_v1_cover_endpoints_need_token(client, anon, services):
    rid = client.get("/api/recipes").json()[0]["id"]
    assert anon.put(f"/api/v1/recipes/{rid}/cover", json={"fuente": "generic"}).status_code == 401
    ro = {"Authorization": "Bearer " + services.tokens.create("r", ["read"])["token"]}
    rw = {"Authorization": "Bearer " + services.tokens.create("w", ["read", "write"])["token"]}
    lib = anon.get("/api/v1/covers/library", headers=ro).json()
    assert lib and all(x["licencia"] for x in lib)
    assert anon.put(f"/api/v1/recipes/{rid}/cover", headers=ro, json={"fuente": "generic"}).status_code in (401, 403)
    r = anon.put(f"/api/v1/recipes/{rid}/cover", headers=rw, json={"fuente": "generic", "biblioteca": lib[0]["id"]})
    assert r.status_code == 200 and r.json()["portada_fuente"] == "generic"
    assert anon.put(f"/api/v1/recipes/{rid}/cover", headers=rw, json={"fuente": "nope"}).status_code == 422
