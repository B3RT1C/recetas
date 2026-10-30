"""Encryption at rest for user secrets (AI API keys) using Fernet.

The key file is generated on first run inside the secret dir (default
~/.recetas-web/secret.key), i.e. OUTSIDE the app/data folder, so copying or
exporting the data never leaks it. Back it up together with data/recetas.db:
without it, stored API keys cannot be decrypted (you just re-enter them).
"""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class SecretBox:
    def __init__(self, secret_dir: Path):
        secret_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = secret_dir / "secret.key"
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            try:
                os.chmod(self.key_path, 0o600)
            except OSError:  # Windows: ACLs of the user profile apply
                pass
        self._fernet = Fernet(self.key_path.read_bytes().strip())

    def encrypt(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str | None:
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError):
            return None


def mask(secret: str | None) -> str | None:
    if not secret:
        return None
    return "••••" + secret[-4:] if len(secret) > 8 else "••••"
