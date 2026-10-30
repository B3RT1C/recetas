"""Web session auth for the UI: middleware + /api/auth/* routes.

Protected: every /api/* route except /api/health, /api/auth/* and /api/v1/* (bearer tokens),
plus /media, /videos and the OpenAPI docs. /mcp keeps its own bearer auth. The SPA shell and
/assets stay public so the login screen can load.
"""
from __future__ import annotations

import hmac
import logging
import secrets
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, SecretStr

from .services.auth import SESSION_COOKIE, SESSION_DAYS, AuthError

log = logging.getLogger("recetas.auth")
SAFE = {"GET", "HEAD", "OPTIONS"}
OPEN_API = ("/api/health", "/api/auth/")
PROTECTED_PREFIXES = ("/api/", "/media/", "/videos/", "/docs", "/redoc", "/openapi.json")


class AuthIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: SecretStr = Field(min_length=1, max_length=200)


class SetupIn(AuthIn):
    code: str = Field(default="", max_length=64)


def _is_https(req: Request) -> bool:
    return req.url.scheme == "https" or req.headers.get("x-forwarded-proto", "").lower() == "https"


def _ip(req: Request) -> str:
    return req.client.host if req.client else "?"


def _same_origin(req: Request) -> bool:
    origin = req.headers.get("origin")
    if not origin or origin == "null":
        return origin is None
    return urlsplit(origin).netloc.lower() == req.headers.get("host", "").lower()


def needs_session(path: str) -> bool:
    if path.startswith("/api/v1/") or path.startswith(OPEN_API) or path == "/api/health":
        return False
    return path.startswith(PROTECTED_PREFIXES)


def install_auth(app: FastAPI, svc) -> None:
    auth = svc.auth
    setup_file = svc.settings.secret_dir / "setup-code.txt"
    state = {"code": None}

    def setup_code() -> str:
        if state["code"] is None:
            state["code"] = secrets.token_hex(4)
            try:
                setup_file.write_text(state["code"] + "\n", encoding="utf-8")
            except OSError:
                pass
            log.warning("No hay administrador. Código de configuración inicial: %s (también en %s). "
                        "O usa: python -m app.cli create-admin", state["code"], setup_file)
        return state["code"]

    if not auth.has_admin():
        setup_code()

    @app.middleware("http")
    async def session_guard(request: Request, call_next):
        path = request.url.path
        if needs_session(path):
            sess = auth.session(request.cookies.get(SESSION_COOKIE))
            if not sess:
                return JSONResponse({"detail": "Inicia sesión para continuar", "login": True}, status_code=401)
            if request.method not in SAFE:
                sent = request.headers.get("x-csrf-token", "")
                if not hmac.compare_digest(sent, sess["csrf"]) or not _same_origin(request):
                    return JSONResponse({"detail": "Petición no válida (CSRF). Recarga la página."}, status_code=403)
            request.state.user = sess
        elif path.startswith("/api/auth/") and request.method not in SAFE and not _same_origin(request):
            return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        return await call_next(request)

    def set_cookie(resp: Response, req: Request, token: str) -> None:
        resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
                        secure=_is_https(req), path="/")

    @app.get("/api/auth/me", tags=["auth"])
    def me(request: Request):
        sess = auth.session(request.cookies.get(SESSION_COOKIE))
        if not sess:
            return {"autenticado": False, "necesita_configuracion": not auth.has_admin()}
        return {"autenticado": True, "usuario": sess["usuario"], "csrf": sess["csrf"]}

    @app.post("/api/auth/login", tags=["auth"])
    def login(body: AuthIn, request: Request, response: Response):
        try:
            token, sess = auth.login(body.username, body.password.get_secret_value(), _ip(request))
        except AuthError as e:
            headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
            raise HTTPException(429 if e.retry_after else 401, str(e), headers=headers) from None
        set_cookie(response, request, token)
        return {"autenticado": True, **sess}

    @app.post("/api/auth/setup", tags=["auth"])
    def setup(body: SetupIn, request: Request, response: Response):
        """First run only: create the admin. Needs the setup code from the server log unless called from localhost."""
        if auth.has_admin():
            raise HTTPException(409, "Ya existe un administrador")
        local = _ip(request) in ("127.0.0.1", "::1", "testclient")
        if not local and not hmac.compare_digest(body.code.strip(), setup_code()):
            raise HTTPException(403, "Código de configuración incorrecto (míralo en el registro del servidor "
                                     "o en setup-code.txt de la carpeta de secretos)")
        try:
            auth.create_admin(body.username, body.password.get_secret_value())
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        setup_file.unlink(missing_ok=True)
        token, sess = auth.login(body.username, body.password.get_secret_value(), _ip(request))
        set_cookie(response, request, token)
        return {"autenticado": True, **sess}

    @app.post("/api/auth/logout", tags=["auth"])
    def logout(request: Request, response: Response):
        auth.logout(request.cookies.get(SESSION_COOKIE))
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"autenticado": False}
