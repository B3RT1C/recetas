"""API tokens for external agents (REST /api/v1 and MCP). Stored as SHA-256 hashes."""
from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from ..db import Database, now


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenService:
    PREFIX = "rct_"

    def __init__(self, db: Database):
        self.db = db

    def create(self, name: str, scopes: list[str]) -> dict:
        token = self.PREFIX + secrets.token_urlsafe(32)
        cur = self.db.execute(
            "INSERT INTO api_tokens(name,prefix,token_hash,scopes,created) VALUES(?,?,?,?,?)",
            (name, token[:10], _hash(token), ",".join(sorted(set(scopes))), now()),
        )
        return {**self.get(cur.lastrowid), "token": token}  # plain token shown ONCE

    def get(self, tid: int) -> dict:
        r = self.db.query("SELECT id,name,prefix,scopes,created,last_used,revoked FROM api_tokens WHERE id=?", (tid,))[0]
        return {**dict(r), "scopes": r["scopes"].split(","), "revoked": bool(r["revoked"])}

    def list(self) -> list[dict]:
        return [self.get(r["id"]) for r in self.db.query("SELECT id FROM api_tokens ORDER BY id DESC")]

    def revoke(self, tid: int) -> bool:
        return self.db.execute("UPDATE api_tokens SET revoked=1 WHERE id=?", (tid,)).rowcount > 0

    def verify(self, token: Optional[str], scope: str = "read") -> Optional[dict]:
        if not token or not token.startswith(self.PREFIX):
            return None
        rows = self.db.query("SELECT id,scopes,revoked FROM api_tokens WHERE token_hash=?", (_hash(token),))
        if not rows or rows[0]["revoked"] or scope not in rows[0]["scopes"].split(","):
            return None
        self.db.execute("UPDATE api_tokens SET last_used=? WHERE id=?", (now(), rows[0]["id"]))
        return self.get(rows[0]["id"])
