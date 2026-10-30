"""Instagram access behind a small interface.

* ``MockInstagramProvider`` — deterministic fake used by the tests and the demo
  screenshots (``RECETAS_IG_PROVIDER=mock``).
* ``InstaloaderProvider`` — real implementation on top of instaloader using the
  user's own session. **Not tested against live Instagram** (no credentials were
  used while building it); Instagram may answer with checkpoints/challenges or
  rate limits, which are surfaced to the UI as readable errors.

Security: the password only lives in memory for the duration of the login call
and is never stored or logged. Only instaloader's session file is persisted, in
the secret dir (outside the data folder).
"""
from __future__ import annotations

import base64
import struct
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Protocol
from urllib.parse import urlparse


class InstagramError(Exception):
    """Readable (Spanish) error shown in the UI. ``code`` is an import-validator code when known."""

    def __init__(self, msg: str = "", code: str | None = None):
        super().__init__(msg)
        self.code = code


@dataclass
class IGCollection:
    id: str
    nombre: str
    total: Optional[int] = None
    portada: Optional[str] = None


@dataclass
class IGPost:
    shortcode: str
    url: str
    autor: str
    caption: str
    miniatura: Optional[str]
    es_video: bool
    video_src: Optional[str] = None
    foto_src: Optional[str] = None
    fecha: Optional[str] = None

    def public(self) -> dict:
        d = asdict(self)
        d.pop("video_src")
        d.pop("foto_src")
        d["caption"] = self.caption[:600]
        return d


@dataclass
class LoginResult:
    estado: str  # "ok" | "2fa"
    usuario: Optional[str] = None
    mensaje: str = ""


class InstagramProvider(Protocol):
    name: str

    def status(self) -> dict: ...
    def login(self, username: str, password: str) -> LoginResult: ...
    def two_factor(self, code: str) -> LoginResult: ...
    def login_with_cookies(self, sessionid: str = "", cookies: str = "") -> LoginResult: ...
    def logout(self) -> None: ...
    def collections(self) -> list[IGCollection]: ...
    def posts(self, collection_id: str) -> list[IGPost]: ...
    def post(self, shortcode: str) -> IGPost: ...
    def download(self, post: IGPost, kind: str, dest: Path) -> Path: ...
    def fetch_thumbnail(self, url: str) -> tuple[bytes, str]: ...


ALLOWED_CDN = ("cdninstagram.com", "fbcdn.net")


def is_cdn_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return urlparse(url).scheme == "https" and any(host == h or host.endswith("." + h) for h in ALLOWED_CDN)


# --------------------------------------------------------------------------- mock
def _png(rgb: tuple[int, int, int], w: int = 48, h: int = 64) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _thumb(emoji: str, c1: str, c2: str) -> str:
    """Sober mock thumbnail: neutral warm card with a line-art plate icon (emoji/colours kept in data, unused)."""
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 400'><rect width='300' height='400' fill='#efe8df'/>"
           "<g fill='none' stroke='#b4a594' stroke-width='6' stroke-linecap='round' stroke-linejoin='round'>"
           "<circle cx='150' cy='200' r='58'/><circle cx='150' cy='200' r='36'/>"
           "<path d='M64 150v34a12 12 0 0 0 12 12v58M76 150v40M88 150v34a12 12 0 0 1-12 12'/>"
           "<path d='M236 254V150c-14 6-20 24-20 44v10h20'/></g></svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


MOCK_POSTS = {
    "C": [
        ("MOCKpasta01", "@cocinaconmarta", "🍝", "#f6a04d", "#e0563b", True,
         "PASTA CREMOSA DE POLLO en 20 minutos!\nPara 4 personas\n\nIngredientes:\n- 400 g de pasta\n- 2 pechugas de pollo\n- 1/2 cebolla\n- 200 ml de nata\n- 2 dientes de ajo\n- Sal y pimienta al gusto\n\nPreparación:\n1. Cuece la pasta 10 minutos.\n2. Dora el pollo con el ajo 8 min.\n3. Añade la nata y mezcla 2 min.\n#pasta #recetasfaciles"),
        ("MOCKtorti02", "@abuela.lola", "🥔", "#f9d976", "#f39f86", True,
         "Tortilla de patatas jugosa 🥔🥚\n\nIngredientes\n• 6 huevos\n• 700 g de patatas\n• 1 cebolla\n• 250 ml de aceite de oliva\n• Sal\n\nElaboración\n1) Pela y corta las patatas en láminas finas.\n2) Confita patata y cebolla a fuego medio 25 minutos.\n3) Escurre, mezcla con el huevo batido y deja reposar 5 min.\n4) Cuaja 3 minutos por cada lado."),
        ("MOCKsalmo03", "@fitfoodspain", "🐟", "#89f7fe", "#66a6ff", True,
         "Salmón al horno con verduras. Cena lista en 25 min 🙌\n- 2 lomos de salmón\n- 1 calabacín\n- 10 tomates cherry\n- 1 cda de aceite\n1. Corta las verduras y colócalas en la bandeja.\n2. Añade el salmón y hornea a 200º 18 minutos."),
        ("MOCKbrown04", "@dulcesdeana", "🍫", "#a18cd1", "#fbc2eb", False,
         "El brownie más fácil del mundo 😍 ¿Quieres la receta? ¡Comenta BROWNIE y te la mando! #postres"),
        ("DPpn4clj0eC", "@brasas.caseras", "🍢", "#fddb92", "#d1fdff", True,
         "Kebab skewers with tortillas (ya está en tu recetario)"),
        ("MOCKcurry05", "@spicekitchen", "🍛", "#ffecd2", "#fcb69f", True,
         "Chickpea curry 🍛 Serves 4\nIngredients:\n- 2 cans chickpeas\n- 400 ml coconut milk\n- 1 onion\n- 2 tbsp curry paste\nMethod:\n1. Fry the onion 5 min.\n2. Add paste, chickpeas and coconut milk, simmer 15 minutes."),
    ],
    "Postres": [
        ("MOCKflan06", "@reposteriafacil", "🍮", "#fbc2eb", "#a6c1ee", True,
         "Flan de huevo casero\nIngredientes: 4 huevos, 500 ml de leche, 100 g de azúcar\nPasos:\n1. Haz un caramelo con 50 g de azúcar 5 min.\n2. Bate el resto y hornea al baño maría 45 minutos."),
        ("MOCKcooki07", "@bakingwithleo", "🍪", "#f6d365", "#fda085", False,
         "Galletas de avena y plátano, solo 3 ingredientes 🍌"),
    ],
}

# Posts only reachable via post()/import-url, to exercise every validator code in tests.
MOCK_SPECIAL = {
    "MOCKnosteps": ("@mockchef", True, "Ensalada rápida\nIngredientes:\n- 1 lechuga\n- 2 tomates\n- 1 cda de aceite"),
    "MOCKempty01": ("@mockchef", False, ""),
}
MOCK_FAILURES = {
    "MOCKprivate": ("La publicación es privada.", "PRIVATE"),
    "MOCKratelim": ("Instagram está limitando las peticiones (429).", "RATE_LIMITED"),
    "MOCKnetwork": ("Error de red al contactar con Instagram.", "NETWORK"),
}


class MockInstagramProvider:
    name = "mock"

    def __init__(self) -> None:
        self.user: Optional[str] = None
        self._pending_2fa: Optional[str] = None
        self.sessions_saved = 0

    def status(self) -> dict:
        return {"conectado": bool(self.user), "usuario": self.user, "proveedor": self.name}

    def login(self, username: str, password: str) -> LoginResult:
        if not username or not password or password == "incorrecta":
            raise InstagramError("Usuario o contraseña incorrectos.")
        if username.endswith("2fa"):
            self._pending_2fa = username
            return LoginResult("2fa", mensaje="Introduce el código de verificación (prueba: 123456).")
        self.user = username
        self.sessions_saved += 1
        return LoginResult("ok", username)

    def two_factor(self, code: str) -> LoginResult:
        if not self._pending_2fa:
            raise InstagramError("No hay ningún inicio de sesión pendiente de verificación.")
        if code.strip() != "123456":
            raise InstagramError("Código de verificación incorrecto.")
        self.user, self._pending_2fa = self._pending_2fa, None
        self.sessions_saved += 1
        return LoginResult("ok", self.user)

    def login_with_cookies(self, sessionid: str = "", cookies: str = "") -> LoginResult:
        if "sessionid" not in cookies and not sessionid:
            raise InstagramError("Falta la cookie sessionid.")
        self.user = "usuario_cookies"
        self.sessions_saved += 1
        return LoginResult("ok", self.user)

    def logout(self) -> None:
        self.user = None

    def _need(self) -> None:
        if not self.user:
            raise InstagramError("Primero conecta tu cuenta de Instagram.")

    def collections(self) -> list[IGCollection]:
        self._need()
        return [IGCollection("all", "Todos los guardados", sum(len(v) for v in MOCK_POSTS.values()))] + [
            IGCollection(k, k, len(v), _thumb(v[0][2], v[0][3], v[0][4])) for k, v in MOCK_POSTS.items()
        ]

    def _mk(self, t) -> IGPost:
        sc, autor, emoji, c1, c2, video, caption = t
        return IGPost(sc, f"https://www.instagram.com/reel/{sc}/", autor, caption, _thumb(emoji, c1, c2), video,
                      video_src=f"mock://{sc}.mp4" if video else None, foto_src=f"mock://{sc}.png", fecha="2026-10-01")

    def posts(self, collection_id: str) -> list[IGPost]:
        self._need()
        if collection_id == "all":
            return [self._mk(t) for v in MOCK_POSTS.values() for t in v]
        if collection_id not in MOCK_POSTS:
            raise InstagramError("Colección no encontrada.")
        return [self._mk(t) for t in MOCK_POSTS[collection_id]]

    def post(self, shortcode: str) -> IGPost:
        for v in MOCK_POSTS.values():
            for t in v:
                if t[0] == shortcode:
                    return self._mk(t)
        if shortcode in MOCK_FAILURES:
            raise InstagramError(*MOCK_FAILURES[shortcode])
        if shortcode in MOCK_SPECIAL:
            autor, video, caption = MOCK_SPECIAL[shortcode]
            return self._mk((shortcode, autor, "", "#ccc", "#999", video, caption))
        raise InstagramError("Publicación no encontrada.", "NOT_FOUND")

    def download(self, post: IGPost, kind: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if kind == "video":
            if not post.video_src:
                raise InstagramError("La publicación no tiene vídeo.")
            dest.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)  # placeholder, not playable
        else:
            dest.write_bytes(_png((240, 140, 60)))
        return dest

    def fetch_thumbnail(self, url: str) -> tuple[bytes, str]:
        raise InstagramError("El proveedor simulado usa miniaturas embebidas.")


# --------------------------------------------------------------------------- real
class InstaloaderProvider:
    """Real provider (UNTESTED LIVE). Uses instaloader's session handling."""

    name = "instaloader"
    PAGE_LIMIT = 300

    def __init__(self, secret_dir: Path):
        import instaloader  # imported lazily so tests never need network

        self._il = instaloader
        self.session_file = secret_dir / "instagram.session"
        self.user_file = secret_dir / "instagram.user"
        self.L = self._new()
        self._pending: Optional[object] = None
        self._cache: dict[str, IGPost] = {}
        self._restore()

    def _new(self):
        return self._il.Instaloader(quiet=True, download_pictures=False, download_videos=False,
                                    download_comments=False, save_metadata=False, max_connection_attempts=1)

    def _restore(self) -> None:
        if self.session_file.exists() and self.user_file.exists():
            try:
                self.L.load_session_from_file(self.user_file.read_text(encoding="utf-8").strip(), str(self.session_file))
            except Exception:  # corrupted/expired session: user must reconnect
                self.L = self._new()

    def _save(self, username: str) -> None:
        self.L.save_session_to_file(str(self.session_file))
        self.user_file.write_text(username, encoding="utf-8")

    def status(self) -> dict:
        return {"conectado": bool(self.L.context.is_logged_in), "usuario": self.L.context.username, "proveedor": self.name}

    def _translate(self, e: Exception) -> InstagramError:
        il = self._il
        if isinstance(e, il.exceptions.BadCredentialsException):
            return InstagramError("Usuario o contraseña incorrectos.")
        if isinstance(e, il.exceptions.TooManyRequestsException):
            return InstagramError("Instagram está limitando las peticiones (429). Espera unos minutos y vuelve a intentarlo.", "RATE_LIMITED")
        if isinstance(e, getattr(il.exceptions, "PrivateProfileNotFollowedException", ())):
            return InstagramError("La publicación es privada.", "PRIVATE")
        if isinstance(e, getattr(il.exceptions, "BadResponseException", ())) or "not found" in str(e).lower():
            return InstagramError("Publicación no encontrada.", "NOT_FOUND")
        if isinstance(e, getattr(il.exceptions, "ConnectionException", ())) and "429" in str(e):
            return InstagramError("Instagram está limitando las peticiones (429).", "RATE_LIMITED")
        if isinstance(e, il.exceptions.LoginRequiredException):
            return InstagramError("La sesión ha caducado: vuelve a conectar Instagram.")
        msg = str(e)
        if "checkpoint" in msg.lower() or "challenge" in msg.lower():
            return InstagramError("Instagram pide una verificación de seguridad (challenge). Ábrelo en la app/navegador, apruébalo y reintenta, o usa la opción de cookies.")
        code = "NETWORK" if isinstance(e, (OSError, getattr(il.exceptions, "ConnectionException", OSError))) else None
        return InstagramError(f"Error de Instagram: {type(e).__name__}", code)

    def login(self, username: str, password: str) -> LoginResult:
        self.L = self._new()
        try:
            self.L.login(username, password)
        except self._il.exceptions.TwoFactorAuthRequiredException:
            self._pending = self.L
            return LoginResult("2fa", mensaje="Introduce el código de verificación de Instagram.")
        except Exception as e:  # noqa: BLE001 — translated, password never included
            raise self._translate(e) from None
        self._save(username)
        return LoginResult("ok", username)

    def two_factor(self, code: str) -> LoginResult:
        if not self._pending:
            raise InstagramError("No hay ningún inicio de sesión pendiente de verificación.")
        try:
            self.L.two_factor_login(code.strip())
        except Exception as e:  # noqa: BLE001
            raise self._translate(e) from None
        self._pending = None
        self._save(self.L.context.username)
        return LoginResult("ok", self.L.context.username)

    def login_with_cookies(self, sessionid: str = "", cookies: str = "") -> LoginResult:
        self.L = self._new()
        jar = self.L.context._session.cookies
        pairs = [p.split("=", 1) for p in cookies.split(";") if "=" in p]
        if sessionid:
            pairs.append(["sessionid", sessionid])
        if not any(k.strip() == "sessionid" for k, _ in pairs):
            raise InstagramError("Falta la cookie sessionid.")
        for k, v in pairs:
            jar.set(k.strip(), v.strip(), domain=".instagram.com", path="/")
        csrf = jar.get("csrftoken")
        if csrf:
            self.L.context._session.headers.update({"X-CSRFToken": csrf})
        try:
            username = self.L.test_login()
        except Exception as e:  # noqa: BLE001
            raise self._translate(e) from None
        if not username:
            raise InstagramError("La cookie no es válida o ha caducado.")
        self.L.context.username = username
        self._save(username)
        return LoginResult("ok", username)

    def logout(self) -> None:
        for f in (self.session_file, self.user_file):
            f.unlink(missing_ok=True)
        self.L = self._new()

    def _need(self) -> None:
        if not self.L.context.is_logged_in:
            raise InstagramError("Primero conecta tu cuenta de Instagram.")

    def collections(self) -> list[IGCollection]:
        self._need()
        out = [IGCollection("all", "Todos los guardados")]
        try:
            data = self.L.context.get_iphone_json("api/v1/collections/list/", {
                "collection_types": '["ALL_MEDIA_AUTO_COLLECTION","MEDIA","AUDIO_AUTO_COLLECTION"]'})
        except Exception as e:  # noqa: BLE001
            raise self._translate(e) from None
        for c in data.get("items", []):
            if c.get("collection_type") == "ALL_MEDIA_AUTO_COLLECTION":
                continue
            cover = (((c.get("cover_media") or {}).get("image_versions2") or {}).get("candidates") or [{}])[0].get("url")
            out.append(IGCollection(str(c["collection_id"]), c.get("collection_name", "?"), c.get("collection_media_count"), cover))
        return out

    def _from_media(self, m: dict) -> IGPost:
        cands = (m.get("image_versions2") or {}).get("candidates") or []
        if not cands and m.get("carousel_media"):
            cands = (m["carousel_media"][0].get("image_versions2") or {}).get("candidates") or []
        videos = m.get("video_versions") or []
        code = m["code"]
        post = IGPost(code, f"https://www.instagram.com/p/{code}/", "@" + (m.get("user") or {}).get("username", ""),
                      ((m.get("caption") or {}) or {}).get("text", "") or "", cands[0]["url"] if cands else None,
                      bool(videos), videos[0]["url"] if videos else None, cands[0]["url"] if cands else None)
        self._cache[code] = post
        return post

    def _from_post(self, p) -> IGPost:
        post = IGPost(p.shortcode, f"https://www.instagram.com/p/{p.shortcode}/", "@" + p.owner_username, p.caption or "",
                      p.url, p.is_video, p.video_url if p.is_video else None, p.url, p.date_utc.isoformat())
        self._cache[p.shortcode] = post
        return post

    def posts(self, collection_id: str) -> list[IGPost]:
        self._need()
        out: list[IGPost] = []
        try:
            if collection_id == "all":
                profile = self._il.Profile.from_username(self.L.context, self.L.context.username)
                for p in profile.get_saved_posts():
                    out.append(self._from_post(p))
                    if len(out) >= self.PAGE_LIMIT:
                        break
                return out
            max_id = None
            while len(out) < self.PAGE_LIMIT:
                params = {"max_id": max_id} if max_id else {}
                data = self.L.context.get_iphone_json(f"api/v1/feed/collection/{collection_id}/posts/", params)
                out += [self._from_media(i["media"]) for i in data.get("items", []) if i.get("media")]
                if not data.get("more_available"):
                    break
                max_id = data.get("next_max_id")
        except InstagramError:
            raise
        except Exception as e:  # noqa: BLE001
            raise self._translate(e) from None
        return out

    def post(self, shortcode: str) -> IGPost:
        if shortcode in self._cache:
            return self._cache[shortcode]
        try:
            return self._from_post(self._il.Post.from_shortcode(self.L.context, shortcode))
        except Exception as e:  # noqa: BLE001
            raise self._translate(e) from None

    def download(self, post: IGPost, kind: str, dest: Path) -> Path:
        url = post.video_src if kind == "video" else post.foto_src
        if not url:
            raise InstagramError("La publicación no tiene ese tipo de contenido.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with self.L.context._session.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 16):
                        fh.write(chunk)
        except Exception as e:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            raise self._translate(e) from None
        tmp.replace(dest)
        return dest

    def fetch_thumbnail(self, url: str) -> tuple[bytes, str]:
        if not is_cdn_url(url):
            raise InstagramError("URL de miniatura no permitida.")
        r = self.L.context._session.get(url, timeout=20)
        r.raise_for_status()
        return r.content, r.headers.get("Content-Type", "image/jpeg")


def make_provider(kind: str, secret_dir: Path) -> InstagramProvider:
    if kind == "mock":
        return MockInstagramProvider()
    return InstaloaderProvider(secret_dir)
