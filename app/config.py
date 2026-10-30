"""Runtime configuration, read from environment variables (all optional).

Precedence: CLI flags (run.py) > real environment variables > .env file > built-in defaults.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_dotenv(text: str) -> dict[str, str]:
    """Tiny .env parser: KEY=VALUE lines, # comments, optional 'export ', single/double quotes."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        out[key] = value
    return out


def config_file_path() -> Path:
    """RECETAS_CONFIG_FILE (production, e.g. C:\\ProgramData\\recetas-web\\config.env) or <repo>/.env."""
    return Path(os.environ.get("RECETAS_CONFIG_FILE") or ROOT / ".env")


def load_dotenv(path: Path | None = None) -> list[str]:
    """Load .env (RECETAS_ENV_FILE or <repo>/.env) without overriding variables already set.

    Returns the names that were applied (never the values: the file may hold secrets)."""
    path = path or config_file_path()
    if not path.is_file():
        return []
    applied = []
    for k, v in parse_dotenv(path.read_text(encoding="utf-8-sig")).items():
        if k not in os.environ:
            os.environ[k] = v
            applied.append(k)
    return applied


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
    # ffmpeg for video covers: full path or command name; empty/missing => covers fall back gracefully.
    ffmpeg: str = field(default_factory=lambda: os.environ.get("RECETAS_FFMPEG", "ffmpeg"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "recetas.db"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.videos_dir, self.media_dir, self.secret_dir):
            d.mkdir(parents=True, exist_ok=True)
