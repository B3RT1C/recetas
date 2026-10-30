
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
