PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100


def test_upload_photo_and_video(client, settings):
    r = client.post("/api/recipes/2/media/foto", files={"file": ("a.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["media"]["foto"] == "/media/recipes/2/foto.png"
    assert client.get("/media/recipes/2/foto.png").content == PNG
    r = client.post("/api/recipes/2/media/foto", files={"file": ("b.jpg", JPG, "image/jpeg")})
    assert r.json()["media"]["foto"] == "/media/recipes/2/foto.jpg"
    assert not (settings.media_dir / "recipes/2/foto.png").exists()  # replaced
    r = client.post("/api/recipes/2/media/video", files={"file": ("v.mp4", MP4, "video/mp4")})
    assert r.json()["media"]["video"] == "/media/recipes/2/video.mp4"
    r = client.delete("/api/recipes/2/media/video")
    assert r.json()["media"]["video"] is None


def test_upload_rejects_wrong_type_even_with_fake_extension(client):
    r = client.post("/api/recipes/2/media/foto", files={"file": ("x.jpg", b"<script>alert(1)</script>", "image/jpeg")})
    assert r.status_code == 415
    r = client.post("/api/recipes/2/media/video", files={"file": ("x.mp4", PNG, "video/mp4")})
    assert r.status_code == 415


def test_upload_size_limit(client, settings):
    big = JPG + b"\x00" * (settings.max_photo_mb * 1024 * 1024)
    r = client.post("/api/recipes/2/media/foto", files={"file": ("big.jpg", big, "image/jpeg")})
    assert r.status_code == 413
    assert not list((settings.media_dir / "recipes/2").glob("*.part"))


def test_upload_unknown_recipe(client):
    assert client.post("/api/recipes/99999/media/foto", files={"file": ("a.png", PNG)}).status_code == 404
