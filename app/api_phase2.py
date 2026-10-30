"""Phase 2 UI routes: shopping lists, pantry, planner, scaling and the Estado panel."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import __version__
from .config import ROOT
from .db import Database
from .migrations import LATEST
from .services import units as U
from .services.shopping import NotFound


class ListIn(BaseModel):
    nombre: str = Field(default="Lista de la compra", max_length=80)


class ListPatch(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=80)
    mostrar_precios: Optional[bool] = None
    notas: Optional[str] = Field(default=None, max_length=2000)


class ItemIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    cantidad: Optional[float] = Field(default=None, ge=0, le=1e6)
    unidad: str = Field(default="", max_length=20)
    nota: str = Field(default="", max_length=300)
    categoria_id: Optional[int] = None
    recurrente: bool = False


class ItemPatch(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=120)
    cantidad: Optional[float] = Field(default=None, ge=0, le=1e6)
    unidad: Optional[str] = Field(default=None, max_length=20)
    nota: Optional[str] = Field(default=None, max_length=300)
    estado: Optional[str] = Field(default=None, pattern="^(pendiente|ya_lo_tengo|comprado)$")
    categoria_id: Optional[int] = None
    recurrente: Optional[bool] = None
    precio_eur: Optional[float] = Field(default=None, ge=0, le=1e5)


class OrderIn(BaseModel):
    ids: list[int] = Field(max_length=2000)
    categoria_id: Optional[int] = None


class NameIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)


class AddRecipeIn(BaseModel):
    receta_id: int
    raciones: Optional[float] = Field(default=None, gt=0, le=200)


class PlanIn(BaseModel):
    fecha: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    comida: str = Field(default="comida", pattern="^(comida|cena)$")
    receta_id: int
    raciones: Optional[float] = Field(default=None, gt=0, le=200)
    nota: str = Field(default="", max_length=200)


class PlanPatch(BaseModel):
    fecha: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    comida: Optional[str] = Field(default=None, pattern="^(comida|cena)$")
    raciones: Optional[float] = Field(default=None, gt=0, le=200)
    nota: Optional[str] = Field(default=None, max_length=200)
    posicion: Optional[int] = Field(default=None, ge=0)


class PlanToListIn(BaseModel):
    lista_id: Optional[int] = None
    inicio: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    fin: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    ids: Optional[list[int]] = None


_commit_cache: dict = {}


def app_commit() -> Optional[str]:
    if "c" not in _commit_cache:
        c = os.environ.get("RECETAS_COMMIT")
        if not c:
            f = ROOT / "COMMIT"
            if f.exists():
                c = f.read_text(encoding="utf-8").strip()[:40]
        if not c and shutil.which("git") and (ROOT / ".git").exists():
            try:
                r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                                   capture_output=True, text=True, timeout=5)
                c = r.stdout.strip() or None
            except (OSError, subprocess.TimeoutExpired):
                c = None
        _commit_cache["c"] = c
    return _commit_cache["c"]


def dir_usage(path) -> dict:
    total, files = 0, 0
    if path.exists():
        for root, _dirs, names in os.walk(path):
            for n in names:
                try:
                    total += os.path.getsize(os.path.join(root, n))
                    files += 1
                except OSError:
                    pass
    return {"ruta": str(path), "bytes": total, "archivos": files}


def register(app: FastAPI, svc, get_or_404) -> None:
    sh, pl = svc.shopping, svc.planner

    def nf(fn, *a, **k):
        try:
            return fn(*a, **k)
        except (NotFound, KeyError):
            raise HTTPException(404, "No encontrado") from None
        except ValueError as e:
            raise HTTPException(422, str(e)) from None

    # ------------------------------------------------------------ scaling
    @app.get("/api/recipes/{rid}/escalar", tags=["recetas"])
    def scale(rid: int, raciones: float = Query(gt=0, le=200)):
        return U.scale_recipe(get_or_404(rid), raciones)

    # ------------------------------------------------------------ shopping lists
    @app.get("/api/compra/listas", tags=["compra"])
    def lists():
        return sh.lists()

    @app.post("/api/compra/listas", status_code=201, tags=["compra"])
    def list_create(body: ListIn):
        return sh.create_list(body.nombre)

    @app.get("/api/compra/listas/{lid}", tags=["compra"])
    def list_get(lid: int):
        return nf(sh.get_list, lid)

    @app.patch("/api/compra/listas/{lid}", tags=["compra"])
    def list_patch(lid: int, body: ListPatch):
        return nf(sh.update_list, lid, body.nombre, body.mostrar_precios, body.notas)

    @app.delete("/api/compra/listas/{lid}", status_code=204, tags=["compra"])
    def list_delete(lid: int):
        nf(sh.delete_list, lid)
        return Response(status_code=204)

    @app.post("/api/compra/listas/{lid}/items", status_code=201, tags=["compra"])
    def item_add(lid: int, body: ItemIn):
        return nf(sh.add_item, lid, body.nombre, body.cantidad, body.unidad, body.nota, body.categoria_id, body.recurrente)

    @app.patch("/api/compra/items/{iid}", tags=["compra"])
    def item_patch(iid: int, body: ItemPatch):
        return nf(sh.update_item, iid, **body.model_dump(exclude_unset=True))

    @app.delete("/api/compra/items/{iid}", status_code=204, tags=["compra"])
    def item_delete(iid: int):
        nf(sh.delete_item, iid)
        return Response(status_code=204)

    @app.post("/api/compra/listas/{lid}/orden", tags=["compra"])
    def item_order(lid: int, body: OrderIn):
        return nf(sh.reorder_items, lid, body.ids, body.categoria_id)

    @app.post("/api/compra/listas/{lid}/limpiar", tags=["compra"])
    def list_clear(lid: int):
        return nf(sh.clear_done, lid)

    @app.post("/api/compra/listas/{lid}/receta", tags=["compra"])
    def list_add_recipe(lid: int, body: AddRecipeIn):
        return nf(sh.add_recipe, lid, get_or_404(body.receta_id), body.raciones)

    @app.delete("/api/compra/listas/{lid}/receta/{rid}", tags=["compra"])
    def list_remove_recipe(lid: int, rid: int):
        return nf(sh.remove_recipe, lid, rid)

    @app.get("/api/compra/listas/{lid}/compartir", tags=["compra"])
    def list_share(lid: int, incluir_tengo: bool = False):
        return nf(sh.share_text, lid, incluir_tengo)

    @app.get("/api/compra/categorias", tags=["compra"])
    def cats():
        return sh.categories()

    @app.post("/api/compra/categorias", status_code=201, tags=["compra"])
    def cat_create(body: NameIn):
        return nf(sh.create_category, body.nombre)

    @app.patch("/api/compra/categorias/{cid}", tags=["compra"])
    def cat_rename(cid: int, body: NameIn):
        return nf(sh.rename_category, cid, body.nombre)

    @app.delete("/api/compra/categorias/{cid}", status_code=204, tags=["compra"])
    def cat_delete(cid: int):
        nf(sh.delete_category, cid)
        return Response(status_code=204)

    @app.post("/api/compra/categorias/orden", tags=["compra"])
    def cat_order(body: OrderIn):
        return sh.reorder_categories(body.ids)

    @app.get("/api/compra/despensa", tags=["compra"])
    def pantry():
        return sh.pantry()

    @app.post("/api/compra/despensa", status_code=201, tags=["compra"])
    def pantry_add(body: NameIn):
        return nf(sh.add_pantry, body.nombre)

    @app.delete("/api/compra/despensa/{pid}", status_code=204, tags=["compra"])
    def pantry_del(pid: int):
        nf(sh.delete_pantry, pid)
        return Response(status_code=204)

    # ------------------------------------------------------------ planner
    @app.get("/api/plan", tags=["planificador"])
    def plan_week(inicio: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
        return nf(pl.week, inicio)

    @app.post("/api/plan", status_code=201, tags=["planificador"])
    def plan_add(body: PlanIn):
        return nf(pl.add, body.fecha, body.comida, body.receta_id, body.raciones, body.nota)

    @app.patch("/api/plan/{pid}", tags=["planificador"])
    def plan_patch(pid: int, body: PlanPatch):
        return nf(pl.update, pid, **body.model_dump(exclude_unset=True))

    @app.delete("/api/plan/{pid}", status_code=204, tags=["planificador"])
    def plan_delete(pid: int):
        nf(pl.delete, pid)
        return Response(status_code=204)

    @app.post("/api/plan/a-lista", tags=["planificador"])
    def plan_to_list(body: PlanToListIn):
        lid = body.lista_id
        if lid is None:
            existing = sh.lists()
            lid = existing[0]["id"] if existing else sh.create_list("Lista de la compra")["id"]
        return nf(pl.to_list, sh, lid, body.inicio, body.fin, body.ids)

    # ------------------------------------------------------------ estado
    cache: dict = {}

    @app.get("/api/estado", tags=["meta"])
    def estado(refrescar: bool = False):
        st = svc.settings
        if refrescar or "disk" not in cache or time.time() - cache["disk"][0] > 60:
            free = shutil.disk_usage(st.data_dir)
            cache["disk"] = (time.time(), {"videos": dir_usage(st.videos_dir), "media": dir_usage(st.media_dir),
                                           "base_de_datos": dir_usage(st.data_dir),
                                           "libre_bytes": free.free, "total_bytes": free.total})
        recs = svc.recipes.all()
        with_sc = [r for r in recs if r.get("shortcode")]
        with_video = [r for r in recs if r["media"]["video"]]
        missing = [{"id": r["id"], "titulo": r.get("titulo"), "shortcode": r["shortcode"]}
                   for r in with_sc if not r["media"]["video"]]
        jobs_mem = sorted((j.public() for j in svc.importer.jobs.values()), key=lambda j: j["creado"], reverse=True)
        log_rows = svc.db.query("SELECT * FROM job_log ORDER BY created DESC LIMIT 10")
        recent = [{"id": r["id"], "tipo": r["kind"], "estado": r["estado"], "creado": r["created"],
                   "terminado": r["finished"], "total": r["total"], "ok": r["ok"], "errores": json.loads(r["errores"])}
                  for r in log_rows]
        return {
            "version": __version__, "commit": app_commit(), "esquema": svc.db.conn.execute("PRAGMA user_version").fetchone()[0],
            "esquema_ultimo": LATEST,
            "disco": cache["disk"][1],
            "videos": {"recetas_con_publicacion": len(with_sc), "con_video_local": len(with_video),
                       "sin_video": len(missing), "faltan": missing[:20], "total_recetas": len(recs)},
            "importaciones": recent,
            "cola": {"importaciones_activas": [j for j in jobs_mem if j["estado"] in ("en_cola", "en_curso")],
                     "portadas": svc.thumbs.status()},
        }
