"""Pydantic schemas. Field names follow the original (Spanish) recetas.json schema."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Ingredient(BaseModel):
    model_config = ConfigDict(extra="allow")
    nombre: str = Field(min_length=1, max_length=200)
    cantidad_1: Optional[str] = None
    cantidad_normal: Optional[str] = None
    cantidad_num: Optional[float] = Field(default=None, ge=0)
    unidad: str = Field(default="ud", max_length=30)
    estimada: bool = False
    precio_eur: Optional[float] = Field(default=None, ge=0)
    # Price provenance (see app/services/prices.py). Absent/None => 'estimado'.
    precio_fuente: Optional[str] = Field(default=None, max_length=60)  # provider id
    precio_super: Optional[str] = Field(default=None, max_length=60)
    precio_fecha: Optional[str] = Field(default=None, max_length=30)


class Step(BaseModel):
    model_config = ConfigDict(extra="allow")
    texto: str = Field(min_length=1, max_length=4000)
    minutos: Optional[int] = Field(default=None, ge=0, le=24 * 60)


class CookLog(BaseModel):
    fecha: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    notas: str = Field(default="", max_length=2000)
    fotos: list[str] = Field(default_factory=list, max_length=10)


class Nutrition(BaseModel):
    """Per serving, always an estimate."""
    kcal: Optional[float] = Field(default=None, ge=0)
    proteinas_g: Optional[float] = Field(default=None, ge=0)
    carbohidratos_g: Optional[float] = Field(default=None, ge=0)
    grasas_g: Optional[float] = Field(default=None, ge=0)
    estimado: bool = True


class RecipeIn(BaseModel):
    """Input for create/update. Unknown keys are preserved (lossless round-trips)."""
    model_config = ConfigDict(extra="allow")
    tipo: Literal["receta", "solo_video"] = "receta"
    titulo: str = Field(min_length=1, max_length=200)
    autor: str = Field(default="", max_length=120)
    video_url: str = Field(default="", max_length=500)
    source_url: Optional[str] = Field(default=None, max_length=1000)
    raciones: Optional[int] = Field(default=None, ge=1, le=100)
    raciones_estimadas: bool = False
    tiempo_total_min: Optional[int] = Field(default=None, ge=0, le=7 * 24 * 60)
    precio_total_eur: Optional[float] = Field(default=None, ge=0)
    precio_racion_eur: Optional[float] = Field(default=None, ge=0)
    ingredientes: list[Ingredient] = Field(default_factory=list, max_length=200)
    pasos: list[Step] = Field(default_factory=list, max_length=200)
    notas: str = Field(default="", max_length=5000)
    pasos_sugeridos: bool = False
    nota: Optional[str] = Field(default=None, max_length=2000)
    etiquetas: list[str] = Field(default_factory=list, max_length=30)
    alergenos: list[str] = Field(default_factory=list, max_length=20)
    nutricion: Optional[Nutrition] = None
    favorito: bool = False
    valoracion: Optional[int] = Field(default=None, ge=0, le=5)
    cocinado: list[CookLog] = Field(default_factory=list, max_length=500)

    @field_validator("source_url")
    @classmethod
    def _src(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip()
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("La URL de origen debe empezar por http:// o https://")
        return v or None

    @field_validator("video_url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("La URL del vídeo debe empezar por http:// o https://")
        return v

    @field_validator("etiquetas")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            t = t.strip().lower()[:40]
            if t and t not in out:
                out.append(t)
        return out


class ExportRequest(BaseModel):
    ids: Optional[list[int]] = None  # None = all
    formato: Literal["json", "json_legacy", "markdown", "html"] = "json"
    con_media: bool = False


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    scopes: list[Literal["read", "write"]] = Field(default_factory=lambda: ["read", "write"])


class AIConfigIn(BaseModel):
    preset: Literal["openai", "openrouter", "ollama", "lmstudio", "custom"] = "custom"
    base_url: str = Field(min_length=8, max_length=300)
    model: str = Field(min_length=1, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=500)  # None = keep current
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def _base(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("La URL base debe empezar por http:// o https://")
        return v


class RecipePatch(BaseModel):
    """Small partial update for quick actions (favorite, rating)."""
    favorito: Optional[bool] = None
    valoracion: Optional[int] = Field(default=None, ge=0, le=5)
