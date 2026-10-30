"""Command line helpers.  Usage:  python -m app.cli create-admin [--username admin] [--replace]"""
from __future__ import annotations

import argparse
import getpass
import sys

from .config import Settings
from .db import Database
from .services.auth import AuthService


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-admin", help="Crea (o con --replace, sustituye) el usuario administrador web")
    c.add_argument("--username", default=None)
    c.add_argument("--replace", action="store_true", help="Sustituye al administrador existente y cierra sus sesiones")
    c.add_argument("--password-stdin", action="store_true", help="Lee la contraseña de stdin (para scripts)")
    a = p.parse_args(argv)
    st = Settings()
    st.ensure_dirs()
    auth = AuthService(Database(st.db_path))
    if auth.has_admin() and not a.replace:
        print("Ya existe un administrador. Usa --replace para sustituirlo.", file=sys.stderr)
        return 1
    user = a.username or input("Usuario [admin]: ").strip() or "admin"
    if a.password_stdin:
        pw = sys.stdin.readline().rstrip("\n")
    else:
        pw = getpass.getpass("Contraseña: ")
        if pw != getpass.getpass("Repite la contraseña: "):
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1
    try:
        auth.create_admin(user, pw, replace=a.replace)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"Administrador '{user}' creado en {st.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
