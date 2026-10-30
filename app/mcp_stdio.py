"""stdio entry point for MCP clients that launch a local process.

Usage:  set RECETAS_API_TOKEN=rct_...   then   python -m app.mcp_stdio
"""
from __future__ import annotations

import os
import sys

from .main import build_services
from .mcp_server import build_mcp


def main() -> None:
    services = build_services()
    info = services.tokens.verify(os.environ.get("RECETAS_API_TOKEN", ""), "read")
    if not info:
        print("RECETAS_API_TOKEN ausente o no válido (créalo en Ajustes → Acceso para agentes).", file=sys.stderr)
        sys.exit(2)
    build_mcp(services, stdio_token=info).run("stdio")


if __name__ == "__main__":
    main()
