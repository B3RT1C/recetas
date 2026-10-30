"""Background import jobs (Instagram -> media files + recipe drafts)."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Optional

from ..config import Settings
from ..db import Database, now
from .ai import AIService
from .instagram import InstagramError, InstagramProvider
from .recipes import DuplicateError, RecipeService

log = logging.getLogger("recetas.import")


@dataclass
class JobItem:
    shortcode: str
    contenido: str  # video | foto | ambos
    estado: str = "pendiente"  # pendiente | descargando | ok | duplicado | error
    mensaje: str = ""
    draft_id: Optional[int] = None


@dataclass
class Job:
    id: str
    items: list[JobItem]
    estado: str = "en_cola"  # en_cola | en_curso | terminado | cancelado
    creado: str = field(default_factory=now)
    terminado: Optional[str] = None
    cancelar: bool = False

    def public(self) -> dict:
        d = asdict(self)
        d.pop("cancelar")
        d["total"] = len(self.items)
        d["hechos"] = sum(1 for i in self.items if i.estado not in ("pendiente", "descargando"))
        d["progreso"] = round(100 * d["hechos"] / d["total"]) if d["total"] else 100
        return d


class ImportService:
    def __init__(self, db: Database, settings: Settings, recipes: RecipeService, ai: AIService,
                 provider: InstagramProvider, delay_s: float = 2.0):
        self.db, self.settings, self.recipes, self.ai = db, settings, recipes, ai
        self.provider = provider
        self.delay_s = delay_s  # polite pause between posts (rate limits)
        self.jobs: dict[str, Job] = {}
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="import")
        self._lock = threading.Lock()

    # -- drafts ------------------------------------------------------------
    def draft_shortcodes(self) -> set[str]:
        return {r["shortcode"] for r in self.db.query("SELECT shortcode FROM drafts WHERE shortcode IS NOT NULL")}

    def drafts(self) -> list[dict]:
        rows = self.db.query("SELECT * FROM drafts ORDER BY id")
        return [{"id": r["id"], "job_id": r["job_id"], "shortcode": r["shortcode"], "creado": r["created"],
                 **json.loads(r["data"])} for r in rows]

    def draft(self, did: int) -> Optional[dict]:
        return next((d for d in self.drafts() if d["id"] == did), None)

    def update_draft(self, did: int, data: dict) -> Optional[dict]:
        cur = self.draft(did)
        if not cur:
            return None
        keep = {k: cur[k] for k in ("foto", "video", "metodo") if k in cur}
        clean = {k: v for k, v in data.items() if k not in ("id", "job_id", "shortcode", "creado")}
        self.db.execute("UPDATE drafts SET data=? WHERE id=?", (json.dumps({**clean, **keep}, ensure_ascii=False), did))
        return self.draft(did)

    def delete_draft(self, did: int) -> bool:
        return self.db.execute("DELETE FROM drafts WHERE id=?", (did,)).rowcount > 0

    def save_draft(self, did: int, data: Optional[dict] = None) -> dict:
        d = self.draft(did)
        if not d:
            raise KeyError(did)
        payload = {**d, **(data or {})}
        payload["shortcode"] = d["shortcode"]
        for k in ("id", "job_id", "creado", "metodo"):
            payload.pop(k, None)
        recipe = self.recipes.create(payload, origen="instagram")  # raises DuplicateError
        self.delete_draft(did)
        return recipe

    # -- jobs --------------------------------------------------------------
    def start(self, selection: list[dict]) -> Job:
        items = [JobItem(s["shortcode"], s.get("contenido", "ambos")) for s in selection]
        job = Job(uuid.uuid4().hex[:12], items)
        self.jobs[job.id] = job
        self._pool.submit(self._run, job)
        return job

    def _run(self, job: Job) -> None:
        job.estado = "en_curso"
        existing = self.recipes.existing_shortcodes() | self.draft_shortcodes()
        for n, item in enumerate(job.items):
            if job.cancelar:
                item.estado, item.mensaje = "error", "Cancelado"
                continue
            if item.shortcode in existing:
                item.estado, item.mensaje = "duplicado", "Ya estaba en el recetario o en borradores"
                continue
            item.estado = "descargando"
            try:
                self._import_one(job, item)
                existing.add(item.shortcode)
            except InstagramError as e:
                item.estado, item.mensaje = "error", str(e)
            except Exception as e:  # noqa: BLE001
                log.exception("import failed for %s", item.shortcode)
                item.estado, item.mensaje = "error", f"Error inesperado: {type(e).__name__}"
            if self.delay_s and n < len(job.items) - 1:
                time.sleep(self.delay_s)
        job.estado = "cancelado" if job.cancelar else "terminado"
        job.terminado = now()
        self._log_job(job)

    def _log_job(self, job: Job) -> None:
        """Persist a summary for the Estado panel (survives restarts)."""
        errs = [{"shortcode": i.shortcode, "mensaje": i.mensaje} for i in job.items if i.estado == "error"][:50]
        try:
            self.db.execute("INSERT OR REPLACE INTO job_log(id,kind,estado,created,finished,total,ok,errores) "
                            "VALUES(?,?,?,?,?,?,?,?)",
                            (job.id, "importacion", job.estado, job.creado, job.terminado, len(job.items),
                             sum(1 for i in job.items if i.estado == "ok"), json.dumps(errs, ensure_ascii=False)))
        except Exception:  # never break an import because of the log
            log.exception("job_log")

    def _import_one(self, job: Job, item: JobItem) -> None:
        post = self.provider.post(item.shortcode)
        media: dict[str, str] = {}
        avisos = []
        if item.contenido in ("video", "ambos"):
            if post.es_video:
                dest = self.settings.videos_dir / f"{post.shortcode}.mp4"  # legacy-compatible layout
                if not dest.exists():
                    self.provider.download(post, "video", dest)
                media["video"] = f"videos/{post.shortcode}.mp4"
            else:
                avisos.append("sin vídeo (es una foto)")
        if item.contenido in ("foto", "ambos"):
            ext = "png" if (post.foto_src or "").endswith(".png") else "jpg"
            dest = self.settings.media_dir / "photos" / f"{post.shortcode}.{ext}"
            self.provider.download(post, "foto", dest)
            media["foto"] = f"media/photos/{post.shortcode}.{ext}"
        draft, metodo = self.ai.extract_recipe(post.caption, autor=post.autor, video_url=post.url)
        draft.update(media, metodo=metodo, caption_original=post.caption[:5000])
        cur = self.db.execute("INSERT INTO drafts(job_id,shortcode,data,created) VALUES(?,?,?,?)",
                              (job.id, post.shortcode, json.dumps(draft, ensure_ascii=False), now()))
        item.draft_id = cur.lastrowid
        item.estado = "ok"
        item.mensaje = ("Receta extraída con IA" if metodo == "ia" else "Receta extraída (heurística)") + \
            (f" · {', '.join(avisos)}" if avisos else "")

    def import_url(self, url: str) -> dict:
        """Synchronous single-post import used by the external API / MCP: saves directly."""
        from ..db import shortcode_of
        sc = shortcode_of(url)
        if not sc:
            raise InstagramError("URL de Instagram no válida.")
        if sc in self.recipes.existing_shortcodes():
            raise DuplicateError(sc)
        post = self.provider.post(sc)
        draft, metodo = self.ai.extract_recipe(post.caption, autor=post.autor, video_url=post.url)
        draft["shortcode"] = sc
        return self.recipes.create(draft, origen=f"api:{metodo}")
