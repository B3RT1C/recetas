"""Runtime configuration, read from environment variables (all optional)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _path(env: str, default: Path) -> Path:
    value = os.environ.get(env)
    return Path(value).expanduser().resolve() if value else default


@dataclass
class Settings:
    host: str = field(default_factory=lambda: os.environ.get("RECETAS_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.environ.get("RECETAS_PORT", "8088")))
    data_dir: Path = field(default_factory=lambda: _path("RECETAS_DATA_DIR", ROOT / "data"))
    # Legacy-compatible layout: videos/<SHORTCODE>.mp4 (same as the v1 site).
    videos_dir: Path = field(default_factory=lambda: _path("RECETAS_VIDEOS_DIR", ROOT / "videos"))
    media_dir: Path = field(default_factory=lambda: _path("RECETAS_MEDIA_DIR", ROOT / "media"))
    # Secrets (Fernet key, Instagram session) live OUTSIDE the data folder.
    secret_dir: Path = field(default_factory=lambda: _path("RECETAS_SECRET_DIR", Path.home() / ".recetas-web"))
    seed_file: Path = field(default_factory=lambda: _path("RECETAS_SEED_FILE", ROOT / "data" / "seed" / "recetas.json"))
    ig_provider: str = field(default_factory=lambda: os.environ.get("RECETAS_IG_PROVIDER", "instaloader"))
    max_photo_mb: int = field(default_factory=lambda: int(os.environ.get("RECETAS_MAX_PHOTO_MB", "10")))
    max_video_mb: int = field(default_factory=lambda: int(os.environ.get("RECETAS_MAX_VIDEO_MB", "300")))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "recetas.db"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.videos_dir, self.media_dir, self.secret_dir):
            d.mkdir(parents=True, exist_ok=True)
