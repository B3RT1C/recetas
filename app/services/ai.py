"""'Conectar tu IA': OpenAI-compatible provider behind an interface (+ fake for tests).

The API key is stored encrypted (SecretBox) and is never returned to the
frontend (only a masked hint), never logged and never exported.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Protocol

import httpx
from pydantic import ValidationError

from ..db import Database
from ..models import RecipeIn
from .caption_parser import parse_caption
from .secrets import SecretBox, mask

log = logging.getLogger("recetas.ai")

PRESETS = {
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "needs_key": True},
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini", "needs_key": True},
    "ollama": {"label": "Ollama (local)", "base_url": "http://localhost:11434/v1", "model": "llama3.1", "needs_key": False},
    "lmstudio": {"label": "LM Studio (local)", "base_url": "http://localhost:1234/v1", "model": "local-model", "needs_key": False},
    "custom": {"label": "Endpoint personalizado", "base_url": "", "model": "", "needs_key": False},
}

RECIPE_SCHEMA_HINT = (
    'Responde SOLO con JSON: {"titulo": str, "raciones": int, "raciones_estimadas": bool, '
    '"ingredientes": [{"nombre": str, "cantidad_num": number|null, "unidad": "g|ml|ud|cda|cdta|taza|diente|pizca|...", '
    '"estimada": bool, "precio_eur": number|null}], "pasos": [{"texto": str, "minutos": int|null}], '
    '"notas": str, "etiquetas": [str]}. Escribe en español de España.'
)


class AIError(Exception):
    pass


class AIProvider(Protocol):
    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str: ...
    def ping(self) -> dict[str, Any]: ...


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, model: str, api_key: Optional[str], timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0.2}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body, headers=self._headers(), timeout=self.timeout)
            if r.status_code == 400 and json_mode:  # some local servers reject response_format
                body.pop("response_format")
                r = httpx.post(f"{self.base_url}/chat/completions", json=body, headers=self._headers(), timeout=self.timeout)
        except httpx.HTTPError as e:
            raise AIError(f"No se pudo conectar con {self.base_url}: {type(e).__name__}") from None
        if r.status_code >= 400:
            raise AIError(f"El proveedor respondió HTTP {r.status_code}")
        try:
            return r.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError):
            raise AIError("Respuesta inesperada del proveedor") from None

    def ping(self) -> dict[str, Any]:
        reply = self.chat([{"role": "user", "content": "Responde solo con la palabra: ok"}])
        return {"ok": True, "respuesta": reply.strip()[:80]}


class FakeAIProvider:
    """Deterministic provider for tests and demos."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages, *, json_mode=False):
        self.calls.append(messages)
        if self.fail:
            raise AIError("fallo simulado")
        prompt = messages[-1]["content"]
        if "TRADUCE" in prompt:
            data = json.loads(prompt.split("\n", 1)[1])
            lang = re.search(r"idioma '([\w-]+)'", prompt)
            data["titulo"] = f"[{lang.group(1) if lang else '?'}] " + data["titulo"]
            return json.dumps(data, ensure_ascii=False)
        if "ESTIMA" in prompt:
            data = json.loads(prompt.split("\n", 1)[1])
            for ing in data.get("ingredientes", []):
                if ing.get("precio_eur") is None:
                    ing["precio_eur"] = 0.5
                if ing.get("cantidad_num") is None:
                    ing["cantidad_num"], ing["estimada"] = 1, True
            return json.dumps(data, ensure_ascii=False)
        return json.dumps({
            "titulo": "Receta extraída por IA", "raciones": 2, "raciones_estimadas": False,
            "ingredientes": [{"nombre": "huevos", "cantidad_num": 2, "unidad": "ud", "estimada": False, "precio_eur": 0.5}],
            "pasos": [{"texto": "Bate los huevos.", "minutos": 2}], "notas": "", "etiquetas": ["huevos"],
        })

    def ping(self):
        if self.fail:
            raise AIError("fallo simulado")
        return {"ok": True, "respuesta": "ok"}


def _json_from(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise AIError("La IA no devolvió JSON")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        raise AIError("La IA devolvió JSON inválido") from None


class AIService:
    SETTING = "ai_config"

    def __init__(self, db: Database, box: SecretBox):
        self.db = db
        self.box = box
        self.override: Optional[AIProvider] = None  # tests inject a FakeAIProvider here

    # -- config ------------------------------------------------------------
    def _raw(self) -> Optional[dict]:
        return self.db.get_setting(self.SETTING)

    def public_config(self) -> dict:
        cfg = self._raw()
        if not cfg:
            return {"configurado": False, "presets": PRESETS}
        key = self.box.decrypt(cfg["api_key_enc"]) if cfg.get("api_key_enc") else None
        return {
            "configurado": True, "enabled": cfg["enabled"], "preset": cfg["preset"], "base_url": cfg["base_url"],
            "model": cfg["model"], "api_key_hint": mask(key), "tiene_api_key": bool(key), "presets": PRESETS,
        }

    def save_config(self, preset: str, base_url: str, model: str, api_key: Optional[str], enabled: bool) -> dict:
        old = self._raw() or {}
        cfg = {"preset": preset, "base_url": base_url, "model": model, "enabled": enabled,
               "api_key_enc": old.get("api_key_enc")}
        if api_key is not None:  # "" clears the key, None keeps it
            cfg["api_key_enc"] = self.box.encrypt(api_key.strip()) if api_key.strip() else None
        self.db.set_setting(self.SETTING, cfg)
        return self.public_config()

    def delete_config(self) -> None:
        self.db.delete_setting(self.SETTING)

    def provider(self) -> Optional[AIProvider]:
        if self.override is not None:
            return self.override
        cfg = self._raw()
        if not cfg or not cfg.get("enabled"):
            return None
        key = self.box.decrypt(cfg["api_key_enc"]) if cfg.get("api_key_enc") else None
        return OpenAICompatibleProvider(cfg["base_url"], cfg["model"], key)

    # -- features ----------------------------------------------------------
    def test(self) -> dict:
        p = self.provider()
        if not p:
            return {"ok": False, "error": "No hay ninguna IA configurada"}
        try:
            return p.ping()
        except AIError as e:
            return {"ok": False, "error": str(e)}

    def extract_recipe(self, caption: str, *, autor: str = "", video_url: str = "") -> tuple[dict, str]:
        """Returns (draft, method) where method is 'ia' or 'heuristico'."""
        heuristic = parse_caption(caption, autor=autor, video_url=video_url)
        p = self.provider()
        if not p or not caption.strip():
            return heuristic, "heuristico"
        try:
            reply = p.chat([
                {"role": "system", "content": "Extraes recetas de descripciones de Instagram. " + RECIPE_SCHEMA_HINT},
                {"role": "user", "content": "EXTRAE la receta de este texto. Si no hay cantidades, déjalas en null.\n" + caption[:8000]},
            ], json_mode=True)
            data = _json_from(reply)
            data.update(autor=autor, video_url=video_url, tipo="receta" if data.get("ingredientes") or data.get("pasos") else "solo_video")
            draft = RecipeIn.model_validate(data).model_dump(exclude_none=True)
            if not draft.get("etiquetas"):
                draft["etiquetas"] = heuristic["etiquetas"]
            return draft, "ia"
        except (AIError, ValidationError) as e:
            log.warning("AI extraction failed, using heuristic parser: %s", type(e).__name__)
            return heuristic, "heuristico"

    def _transform(self, verb: str, recipe: dict, instruction: str) -> dict:
        p = self.provider()
        if not p:
            raise AIError("No hay ninguna IA configurada")
        payload = {k: v for k, v in recipe.items() if k not in ("id", "media", "shortcode", "foto", "video")}
        reply = p.chat([
            {"role": "system", "content": "Trabajas con recetas en JSON. Devuelve el MISMO JSON con los cambios pedidos, sin texto extra."},
            {"role": "user", "content": f"{verb}: {instruction}\n" + json.dumps(payload, ensure_ascii=False)},
        ], json_mode=True)
        data = _json_from(reply)
        try:
            return RecipeIn.model_validate({**payload, **data}).model_dump(exclude_none=True)
        except ValidationError:
            raise AIError("La IA devolvió una receta inválida") from None

    def translate(self, recipe: dict, lang: str) -> dict:
        return self._transform("TRADUCE", recipe, f"traduce títulos, ingredientes, pasos y notas al idioma '{lang}'.")

    def estimate(self, recipe: dict) -> dict:
        out = self._transform(
            "ESTIMA", recipe,
            "rellena cantidad_num/unidad que falten (marca estimada=true) y precio_eur de cada ingrediente "
            "con precios típicos de supermercado en España; recalcula precio_total_eur y precio_racion_eur.",
        )
        out["precios_estimados_ia"] = True
        return out
