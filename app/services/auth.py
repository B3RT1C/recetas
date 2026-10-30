"""Single-admin web login: argon2 hashes, server-side sessions, CSRF tokens, brute-force throttling."""
from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from ..db import Database, now

SESSION_COOKIE = "recetas_session"
SESSION_DAYS = 30
WINDOW_S = 15 * 60          # failures counted in this window
FREE_FAILS = 5              # failures allowed before a lockout kicks in
BASE_LOCK_S = 30            # first lockout; doubles per extra failure
MAX_LOCK_S = 60 * 60
MIN_PASSWORD = 10


class AuthError(Exception):
    def __init__(self, msg: str, retry_after: int = 0):
        super().__init__(msg)
        self.retry_after = retry_after


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class AuthService:
    def __init__(self, db: Database, clock=time.time):
        self.db = db
        self.ph = PasswordHasher()
        self.clock = clock

    # -- users -------------------------------------------------------------
    def has_admin(self) -> bool:
        return bool(self.db.query("SELECT 1 FROM users LIMIT 1"))

    def create_admin(self, username: str, password: str, replace: bool = False) -> dict:
        username = username.strip()
        if not username or len(username) > 60:
            raise ValueError("Nombre de usuario no válido")
        if len(password) < MIN_PASSWORD:
            raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres")
        with self.db._lock:
            if self.has_admin():
                if not replace:
                    raise ValueError("Ya existe un administrador")
                self.db.execute("DELETE FROM users")  # cascades to sessions
            self.db.execute("INSERT INTO users(username,pw_hash,created) VALUES(?,?,?)",
                            (username, self.ph.hash(password), now()))
        return {"usuario": username}

    # -- throttling --------------------------------------------------------
    def _lock_left(self, column: str, value: str) -> int:
        t = self.clock()
        rows = self.db.query(f"SELECT ts, ok FROM login_attempts WHERE {column}=? AND ts>? ORDER BY ts",
                             (value, t - MAX_LOCK_S))
        fails, last = 0, 0.0
        for r in rows:  # consecutive failures since the last success
            fails = 0 if r["ok"] else fails + 1
            last = r["ts"]
        recent = sum(1 for r in rows if not r["ok"] and r["ts"] > t - WINDOW_S)
        if fails < FREE_FAILS or recent < FREE_FAILS:
            return 0
        lock = min(MAX_LOCK_S, BASE_LOCK_S * 2 ** (fails - FREE_FAILS))
        return max(0, int(last + lock - t + 0.999))

    def check_throttle(self, ip: str, username: str) -> None:
        left = max(self._lock_left("ip", ip), self._lock_left("username", username.lower()))
        if left:
            raise AuthError(f"Demasiados intentos fallidos. Vuelve a intentarlo en {left} s.", left)

    def _record(self, ip: str, username: str, ok: bool) -> None:
        t = self.clock()
        self.db.execute("INSERT INTO login_attempts(ip,username,ts,ok) VALUES(?,?,?,?)", (ip, username.lower(), t, int(ok)))
        self.db.execute("DELETE FROM login_attempts WHERE ts<?", (t - 24 * 3600,))

    # -- sessions ----------------------------------------------------------
    def login(self, username: str, password: str, ip: str) -> tuple[str, dict]:
        self.check_throttle(ip, username)
        rows = self.db.query("SELECT * FROM users WHERE username=?", (username.strip(),))
        ok = False
        if rows:
            try:
                ok = self.ph.verify(rows[0]["pw_hash"], password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                ok = False
        else:
            try:  # equalise timing for unknown users
                self.ph.verify(self.ph.hash("x" * MIN_PASSWORD), password)
            except VerifyMismatchError:
                pass
        self._record(ip, username, ok)
        if not ok:
            raise AuthError("Usuario o contraseña incorrectos")
        user = rows[0]
        if self.ph.check_needs_rehash(user["pw_hash"]):
            self.db.execute("UPDATE users SET pw_hash=? WHERE id=?", (self.ph.hash(password), user["id"]))
        self.db.execute("UPDATE users SET last_login=? WHERE id=?", (now(), user["id"]))
        return self.new_session(user["id"], ip)

    def new_session(self, user_id: int, ip: str = "") -> tuple[str, dict]:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        n = datetime.now(timezone.utc)
        self.db.execute("INSERT INTO sessions(id_hash,user_id,csrf,created,expires,ip) VALUES(?,?,?,?,?,?)",
                        (_h(token), user_id, csrf, _iso(n), _iso(n + timedelta(days=SESSION_DAYS)), ip))
        self.db.execute("DELETE FROM sessions WHERE expires<?", (_iso(n),))
        return token, self.session(token)

    def session(self, token: Optional[str]) -> Optional[dict]:
        if not token:
            return None
        rows = self.db.query("SELECT s.csrf, s.expires, u.username FROM sessions s JOIN users u ON u.id=s.user_id "
                             "WHERE s.id_hash=?", (_h(token),))
        if not rows or rows[0]["expires"] < _iso(datetime.now(timezone.utc)):
            return None
        return {"usuario": rows[0]["username"], "csrf": rows[0]["csrf"]}

    def logout(self, token: Optional[str]) -> None:
        if token:
            self.db.execute("DELETE FROM sessions WHERE id_hash=?", (_h(token),))
