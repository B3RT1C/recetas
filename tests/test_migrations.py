import json
import sqlite3
from pathlib import Path

from app.db import Database
from app.migrations import LATEST

FIX = Path(__file__).parent / "fixtures" / "schema_b721dc9.sql"


def make_v0(path: Path):
    c = sqlite3.connect(path)
    c.executescript(FIX.read_text())
    c.execute("INSERT INTO recipes(id,tipo,shortcode,legacy_order,data) VALUES(7,'receta','ABC',0,?)",
              (json.dumps({"titulo": "Tortilla", "raciones": 2}),))
    c.execute("INSERT INTO meta(key,value) VALUES('seeded','x')")
    c.execute("INSERT INTO shopping_lists(name,created,updated) VALUES('Semana','t','t')")
    c.execute("INSERT INTO shopping_items(list_id,name,name_norm,qty,unit,status,sources,updated) "
              "VALUES(1,'Huevos','huevo',6,'ud','pendiente','[]','t')")
    c.commit()
    assert c.execute("PRAGMA user_version").fetchone()[0] == 0
    c.close()


def test_upgrade_from_b721dc9_preserves_data(tmp_path):
    p = tmp_path / "recetas.db"
    make_v0(p)
    db = Database(p)
    assert db.migrated_from == 0
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == LATEST
    assert json.loads(db.query("SELECT data FROM recipes WHERE id=7")[0]["data"])["titulo"] == "Tortilla"
    it = db.query("SELECT * FROM shopping_items")[0]
    assert it["name"] == "Huevos" and it["price_eur"] is None
    for t in ("users", "sessions", "plan_items", "pantry", "login_attempts", "job_log"):
        db.query(f"SELECT * FROM {t}")
    assert db.query("SELECT count(*) n FROM shopping_categories")[0]["n"] > 5
    assert db.backup_path and db.backup_path.exists()
    db.conn.close()
    # second start: nothing to do, idempotent
    db2 = Database(p)
    assert db2.migrated_from == LATEST and db2.backup_path is None


def test_fresh_db_is_latest(tmp_path):
    db = Database(tmp_path / "n.db")
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == LATEST
