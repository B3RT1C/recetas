"""Price model (ready for real supermarket prices in a later phase).

Each ingredient price may carry: precio_fuente ('estimado' | 'superfudis' | 'manual'),
precio_super (supermarket name) and precio_fecha (ISO date). The UI shows
'real (fuente, fecha)' when precio_fuente != 'estimado', otherwise 'estimado'.

A per-ingredient cache (table `price_cache`) stores normalized prices so a future
provider (e.g. Superfudis compare-basket: max 10 products/request, ~3 req/min)
can be queried sparingly. `match_override` lets the user pin the product used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional, Protocol

from ..db import Database, now
from .tags import norm

Source = str  # provider id; built-ins: "estimado", "superfudis", "manual"
BUILTIN_PROVIDERS = ("superfudis", "estimado")

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_cache (
  ingredient TEXT NOT NULL,            -- normalized ingredient name
  supermarket TEXT NOT NULL DEFAULT '',
  price_per_kg REAL, price_per_l REAL, price_per_unit REAL,
  source TEXT NOT NULL,                -- provider id: 'estimado' | 'superfudis' | 'manual' | user provider id
  unit TEXT, package_size REAL, url TEXT,
  fetched_at TEXT NOT NULL,
  match_override TEXT,                 -- product id/name the user pinned
  PRIMARY KEY (ingredient, supermarket)
);
"""


@dataclass
class PriceEntry:
    ingredient: str
    supermarket: str = ""
    price_per_kg: Optional[float] = None
    price_per_l: Optional[float] = None
    price_per_unit: Optional[float] = None
    source: Source = "estimado"
    fetched_at: str = ""
    match_override: Optional[str] = None
    unit: Optional[str] = None
    package_size: Optional[float] = None
    url: Optional[str] = None


@dataclass
class ProviderConfig:
    """User-defined price API ('Conectar tu API de precios' in Ajustes). Stored as a
    setting; `auth_value` is Fernet-encrypted like AI keys and never sent to the UI
    nor included in the JSON export of provider configs."""
    id: str
    label: str
    base_url: str
    method: Literal["GET", "POST"] = "POST"
    auth_header: str = "Authorization"
    auth_value_enc: Optional[str] = None
    request_template: str = '{"query": "{ingrediente}", "quantity": "{cantidad}"}'
    response_map: dict = field(default_factory=lambda: {   # JSON-paths
        "price": "$.price", "unit": "$.unit", "package_size": "$.size",
        "supermarket": "$.store", "url": "$.url"})
    priority: int = 100          # lower = tried first; fallback down the list
    rate_limit_per_min: float = 3
    max_batch: int = 1
    enabled: bool = True


class PriceProvider(Protocol):
    name: str
    max_batch: int          # e.g. 10 for Superfudis
    min_interval_s: float   # e.g. 20 s (~3 req/min)

    def lookup(self, ingredients: list[str]) -> list[PriceEntry]: ...


class PriceRouter:
    """Tries providers by priority with fallback; results go to the shared cache.
    Built-ins: 'superfudis' (later phase) and 'estimado' (always last)."""

    def __init__(self, cache: "PriceCache", providers: list[PriceProvider]):
        self.cache, self.providers = cache, providers

    def lookup(self, ingredient: str) -> Optional[PriceEntry]:
        hit = self.cache.get(ingredient)
        if hit:
            return hit[0]
        for p in self.providers:
            try:
                found = p.lookup([ingredient])
            except Exception:  # noqa: BLE001 - fall back to the next provider
                continue
            if found:
                self.cache.put(found[0])
                return found[0]
        return None


class PriceCache:
    def __init__(self, db: Database):
        self.db = db
        with db._lock:
            db.conn.executescript(SCHEMA)

    def get(self, ingredient: str) -> list[PriceEntry]:
        rows = self.db.query("SELECT * FROM price_cache WHERE ingredient=?", (norm(ingredient),))
        return [PriceEntry(**dict(r)) for r in rows]

    def put(self, e: PriceEntry) -> None:
        e.ingredient, e.fetched_at = norm(e.ingredient), e.fetched_at or now()
        d = asdict(e)
        self.db.execute(f"INSERT OR REPLACE INTO price_cache ({','.join(d)}) VALUES ({','.join('?' * len(d))})",
                        tuple(d.values()))


def price_label(ing: dict) -> str:
    src = ing.get("precio_fuente") or "estimado"
    if src == "estimado":
        return "estimado"
    bits = [b for b in (ing.get("precio_super") or src, (ing.get("precio_fecha") or "")[:10]) if b]
    return f"real ({', '.join(bits)})"
