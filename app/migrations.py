"""Forward-only schema migrations, applied automatically on startup.

`SCHEMA` in db.py is the baseline shipped in b721dc9 (user_version 0) and is only ever
`CREATE ... IF NOT EXISTS`. Every later change is a numbered step here; `PRAGMA user_version`
records the last applied one. Rules: never drop or rename columns/tables, only add; each step
is idempotent and runs inside one transaction; before migrating an existing non-empty database a
copy is written next to it (recetas.db.bak-v<N>) so an upgrade can always be rolled back by hand.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Callable

log = logging.getLogger("recetas.db")

DEFAULT_CATEGORIES = ["Fruta y verdura", "Carne", "Pescado y marisco", "Lácteos y huevos", "Panadería y cereales",
                      "Despensa", "Especias y condimentos", "Congelados", "Bebidas", "Droguería y hogar", "Otros"]


def _cols(c: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}


def _add_col(c: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    if col not in _cols(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def m1_phase2(c: sqlite3.Connection) -> None:
    """Shopping lists (full), pantry, planner, web login, job log."""
    c.executescript("""
    CREATE TABLE IF NOT EXISTS pantry (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, name_norm TEXT NOT NULL UNIQUE, created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS plan_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, comida TEXT NOT NULL DEFAULT 'comida',
      recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE, raciones REAL NOT NULL DEFAULT 2,
      nota TEXT, position INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_plan_fecha ON plan_items(fecha);
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, pw_hash TEXT NOT NULL,
      created TEXT NOT NULL, last_login TEXT);
    CREATE TABLE IF NOT EXISTS sessions (
      id_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      csrf TEXT NOT NULL, created TEXT NOT NULL, expires TEXT NOT NULL, ip TEXT);
    CREATE TABLE IF NOT EXISTS login_attempts (
      id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT NOT NULL, username TEXT NOT NULL, ts REAL NOT NULL, ok INTEGER NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_login_ip ON login_attempts(ip, ts);
    CREATE INDEX IF NOT EXISTS ix_login_user ON login_attempts(username, ts);
    CREATE TABLE IF NOT EXISTS job_log (
      id TEXT PRIMARY KEY, kind TEXT NOT NULL, estado TEXT NOT NULL, created TEXT NOT NULL, finished TEXT,
      total INTEGER NOT NULL DEFAULT 0, ok INTEGER NOT NULL DEFAULT 0, errores TEXT NOT NULL DEFAULT '[]');
    """)
    _add_col(c, "shopping_lists", "position", "INTEGER NOT NULL DEFAULT 0")
    _add_col(c, "shopping_lists", "notes", "TEXT")
    _add_col(c, "shopping_items", "price_eur", "REAL")          # orientative, from the price provider
    _add_col(c, "shopping_items", "price_source", "TEXT")       # provider id ('estimado' for now)
    _add_col(c, "shopping_items", "created", "TEXT")
    if not c.execute("SELECT 1 FROM shopping_categories").fetchone():
        c.executemany("INSERT OR IGNORE INTO shopping_categories(name, position) VALUES(?,?)",
                      [(n, i) for i, n in enumerate(DEFAULT_CATEGORIES)])


def m2_price_history(c: sqlite3.Connection) -> None:
    """Append-only price history (one row per price change), groundwork for Fase 3 price features."""
    c.executescript("""
    CREATE TABLE IF NOT EXISTS price_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT, ingredient TEXT NOT NULL, supermarket TEXT NOT NULL DEFAULT '',
      source TEXT NOT NULL, price_per_kg REAL, price_per_l REAL, price_per_unit REAL, recorded_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_price_history ON price_history(ingredient, supermarket, recorded_at);
    """)


def m3_cover_source(c: sqlite3.Connection) -> None:
    """v2.1.2: per-recipe cover choice. NULL = follow the global default (Ajustes).

    cover_source: original | frame | upload | generic; cover_param: frame seconds, library id or upload path.
    Imports/reimports never write these columns, so a manual choice survives a reimport."""
    _add_col(c, "recipes", "cover_source", "TEXT CHECK (cover_source IN ('original','frame','upload','generic'))")
    _add_col(c, "recipes", "cover_param", "TEXT")


MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [m1_phase2, m2_price_history, m3_cover_source]
LATEST = len(MIGRATIONS)


def migrate(conn: sqlite3.Connection, path: Path | None = None) -> tuple[int, Path | None]:
    """Apply pending migrations. Returns (version before, backup path or None)."""
    cur = conn.execute("PRAGMA user_version").fetchone()[0]
    if cur > LATEST:
        raise RuntimeError(f"La base de datos es de una versión más nueva ({cur} > {LATEST}); actualiza la aplicación.")
    backup = None
    if cur < LATEST and path and path.exists() and conn.execute("SELECT count(*) FROM recipes").fetchone()[0]:
        backup = path.with_name(f"{path.name}.bak-v{cur}")
        if not backup.exists():
            dst = sqlite3.connect(str(backup))
            conn.backup(dst)
            dst.close()
        log.info("Copia de seguridad antes de migrar: %s", backup)
    for v in range(cur, LATEST):
        with conn:
            MIGRATIONS[v](conn)
            conn.execute(f"PRAGMA user_version={v + 1}")
        log.info("Migración %d aplicada", v + 1)
    return cur, backup
