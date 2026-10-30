"""Ajustes → Acceso: detected URLs + QR (read-only) and admin editing of host/port.

All routes live under /api/ so the session middleware enforces login (single admin) and CSRF on PUT.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

from .services import access as A


class NetIn(BaseModel):
    host: str
    port: int | str


def register(app: FastAPI, svc, ops: A.SystemOps | None = None) -> None:
    st = svc.settings
    cfg = os.environ.get("RECETAS_CONFIG_FILE")
    app.state.access_ops = ops or A.SystemOps(Path(cfg) if cfg else None)

    def cur():
        return st.host, int(st.port)

    @app.get("/api/acceso", tags=["ajustes"])
    def acceso():
        host, port = cur()
        o = app.state.access_ops
        return {"host": host, "port": port, "urls": A.access_urls(host, port),
                "archivo_config": str(o.config_file or A.config_file_path()),
                "reinicio_automatico": o.enabled, "aviso": o.unavailable_reason()}

    @app.get("/api/acceso/qr", tags=["ajustes"])
    def acceso_qr(url: str):
        host, port = cur()
        if url not in {u["url"] for u in A.access_urls(host, port)}:
            raise HTTPException(400, "URL no reconocida")
        return Response(A.qr_svg(url), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})

    @app.put("/api/acceso/red", tags=["ajustes"])
    def acceso_red(body: NetIn):
        h0, p0 = cur()
        try:
            host, port = A.validate(body.host, body.port, h0, p0)
        except A.ConfigError as e:
            raise HTTPException(422, str(e)) from None
        o = app.state.access_ops
        path = o.config_file or A.config_file_path()
        A.write_config(path, {"RECETAS_HOST": host, "RECETAS_PORT": str(port)})
        msgs = []
        if not o.enabled:
            msgs.append(o.unavailable_reason())
            return {"guardado": True, "reiniciando": False, "host": host, "port": port, "mensajes": msgs,
                    "urls": A.access_urls(host, port)}
        if port != p0:
            if not o.add_firewall(port):
                msgs.append("No se pudieron crear las reglas del cortafuegos para el nuevo puerto.")
            # old rules are removed only once the new server answers /api/health
            A.pending_cleanup_file(st.secret_dir).write_text(f"{p0},{port}", encoding="utf-8")
        restarting = o.restart()
        if not restarting:
            msgs.append("No se pudo lanzar la tarea RecetasWeb; reinicia el servicio a mano.")
        return {"guardado": True, "reiniciando": restarting, "host": host, "port": port, "mensajes": msgs,
                "urls": A.access_urls(host, port)}

    state = {"cleaned": False}

    @app.middleware("http")
    async def _health_cleanup(request, call_next):
        resp = await call_next(request)
        if not state["cleaned"] and request.url.path == "/api/health" and resp.status_code == 200:
            state["cleaned"] = True
            try:
                A.cleanup_old_rules(app.state.access_ops, st.secret_dir, int(st.port))
            except Exception:  # never break health checks
                pass
        return resp
