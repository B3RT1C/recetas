"""SQLite storage.

Why SQLite: it ships with Python (zero extra deps on Windows), gives atomic writes
(background import jobs + the web UI write concurrently), and lets us keep each
recipe as a lossless JSON document while indexing the few columns we query on.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .services.tags import suggest_allergens, suggest_tags

SHORTCODE_RE = re.compile(r"/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)")
# Keys added by v2 on top of the legacy recetas.json schema (stripped by the legacy export).
V2_KEYS = ("etiquetas", "foto", "video", "origen", "creado", "actualizado", "caption_original", "precios_estimados_ia",
           "alergenos", "nutricion", "favorito", "valoracion", "cocinado")
# Recipe status: v1 "solo en vídeo" dishes are recipes still waiting to be transcribed.
ESTADO_COMPLETA = "completa"
ESTADO_PENDIENTE = "pendiente de transcribir"

SCHEMA = """
-- Shopping (later phase; schema ready). Personal lists, not tied to any supermarket.
CREATE TABLE IF NOT EXISTS shopping_lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created TEXT NOT NULL, updated TEXT,
  show_prices INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1   -- version: optimistic sync later
);
CREATE TABLE IF NOT EXISTS shopping_categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS shopping_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  list_id INTEGER NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
  category_id INTEGER REFERENCES shopping_categories(id) ON DELETE SET NULL,
  name TEXT NOT NULL, name_norm TEXT NOT NULL,          -- aggregation key
  qty REAL, unit TEXT,                                  -- canonical unit after conversion (g/ml/ud...)
  status TEXT NOT NULL DEFAULT 'pendiente' CHECK (status IN ('pendiente','ya_lo_tengo','comprado')),
  note TEXT, position INTEGER NOT NULL DEFAULT 0,
  sources TEXT NOT NULL DEFAULT '[]',                   -- json [{recipe_id, servings, qty, unit}] or [] if manual
  recurring INTEGER NOT NULL DEFAULT 0,                 -- pantry / recurring item
  updated TEXT, version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('receta','solo_video')),
    shortcode TEXT UNIQUE,
    legacy_order INTEGER,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    shortcode TEXT,
    data TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    scopes TEXT NOT NULL DEFAULT 'read,write',
    created TEXT NOT NULL,
    last_used TEXT,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def shortcode_of(url: str | None) -> str | None:
    m = SHORTCODE_RE.search(url or "")
    return m.group(1) if m else None


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # -- helpers -----------------------------------------------------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock, self.conn:
            return self.conn.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, tuple(params)).fetchall()

    # -- meta / settings ---------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        rows = self.query("SELECT value FROM meta WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def set_meta(self, key: str, value: str) -> None:
        self.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def get_setting(self, key: str) -> Any:
        rows = self.query("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else None

    def set_setting(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    def delete_setting(self, key: str) -> None:
        self.execute("DELETE FROM settings WHERE key=?", (key,))

    # -- migration ---------------------------------------------------------
    def seed_from_legacy(self, seed_file: Path) -> int:
        """Import the v1 recetas.json once, losslessly (every original key is kept)."""
        if self.get_meta("seeded") or not seed_file.exists():
            return 0
        legacy = json.loads(seed_file.read_text(encoding="utf-8"))
        meta = {k: v for k, v in legacy.items() if k not in ("recetas", "solo_video")}
        count = 0
        with self._lock, self.conn:
            for order, rec in enumerate(legacy.get("recetas", [])):
                data = {k: v for k, v in rec.items() if k != "id"}
                data.update(etiquetas=suggest_tags(rec), alergenos=suggest_allergens(rec), origen="instagram:C", creado=now())
                self.conn.execute(
                    "INSERT INTO recipes(id,tipo,shortcode,legacy_order,data) VALUES(?,?,?,?,?)",
                    (rec["id"], "receta", shortcode_of(rec.get("video_url")), order, json.dumps(data, ensure_ascii=False)),
                )
                count += 1
            for order, rec in enumerate(legacy.get("solo_video", [])):
                data = dict(rec)
                data.update(etiquetas=suggest_tags(rec), origen="instagram:C", creado=now())
                sc = shortcode_of(rec.get("video_url"))
                if sc and self.conn.execute("SELECT 1 FROM recipes WHERE shortcode=?", (sc,)).fetchone():
                    sc = None  # keep the entry, just don't violate the unique index
                self.conn.execute(
                    "INSERT INTO recipes(tipo,shortcode,legacy_order,data) VALUES(?,?,?,?)",
                    ("solo_video", sc, order, json.dumps(data, ensure_ascii=False)),
                )
                count += 1
        self.set_meta("legacy_meta", json.dumps(meta, ensure_ascii=False))
        self.set_meta("seeded", now())
        return count
