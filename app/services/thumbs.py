"""Card covers: grab one frame from each local video with ffmpeg, in a background thread.

Thumbnails are cached as media/thumbs/<key>.jpg (key = shortcode, or r<id> for manual recipes).
Fallback order for a card cover: video frame -> imported photo/thumbnail -> null (UI shows a neutral line-icon placeholder).
If ffmpeg is missing (RECETAS_FFMPEG unset and not on PATH) nothing breaks; the Estado panel says so.
"""
from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from ..config import Settings

log = logging.getLogger("recetas.thumbs")
WIDTH = 480


class ThumbService:
    def __init__(self, settings: Settings, autostart: bool = True):
        self.settings = settings
        self.dir = settings.media_dir / "thumbs"
        self.q: "queue.Queue[tuple[str, Path]]" = queue.Queue()
        self.pending: set[str] = set()
        self.failed: dict[str, str] = {}
        self.done = 0
        self.errors: list[dict] = []
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self.autostart = autostart

    # -- ffmpeg ------------------------------------------------------------
    def ffmpeg_path(self) -> Optional[str]:
        cand = (self.settings.ffmpeg or "").strip().strip('"')
        if not cand:
            return None
        if os.path.sep in cand or (os.altsep and os.altsep in cand):
            return cand if Path(cand).is_file() else None
        return shutil.which(cand)

    def available(self) -> bool:
        return self.ffmpeg_path() is not None

    # -- covers ------------------------------------------------------------
    def path_for(self, key: str) -> Path:
        safe = "".join(c for c in key if c.isalnum() or c in "-_")
        return self.dir / f"{safe}.jpg"

    def cover(self, key: str, video: Optional[Path], foto_url: Optional[str]) -> Optional[str]:
        p = self.path_for(key)
        if p.exists() and (video is None or not video.exists() or p.stat().st_mtime >= video.stat().st_mtime):
            return f"/media/thumbs/{p.name}?v={int(p.stat().st_mtime)}"
        if video is not None and video.exists():
            self.enqueue(key, video)
        return foto_url

    def enqueue(self, key: str, video: Path) -> bool:
        if not self.available() or key in self.failed:
            return False
        with self._lock:
            if key in self.pending:
                return False
            self.pending.add(key)
        self.q.put((key, video))
        if self.autostart:
            self._ensure_worker()
        return True

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, name="thumbs", daemon=True)
                self._worker.start()

    def _run(self) -> None:
        while True:
            try:
                key, video = self.q.get(timeout=5)
            except queue.Empty:
                return
            try:
                self.extract(key, video)
            finally:
                with self._lock:
                    self.pending.discard(key)
                self.q.task_done()

    def drain(self, timeout: float = 30) -> None:
        """Process the queue synchronously (tests, CLI)."""
        t0 = time.time()
        while not self.q.empty() and time.time() - t0 < timeout:
            key, video = self.q.get()
            try:
                self.extract(key, video)
            finally:
                with self._lock:
                    self.pending.discard(key)
                self.q.task_done()

    def extract(self, key: str, video: Path) -> bool:
        exe = self.ffmpeg_path()
        if not exe:
            return False
        self.dir.mkdir(parents=True, exist_ok=True)
        out = self.path_for(key)
        tmp = out.with_suffix(".part.jpg")
        err = ""
        for ss in ("1", "0"):  # very short clips have no frame at 1 s
            cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-ss", ss, "-i", str(video),
                   "-frames:v", "1", "-vf", f"scale={WIDTH}:-2", "-q:v", "4", str(tmp)]
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=60)
                err = r.stderr.decode(errors="replace")[-300:]
                if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
                    os.replace(tmp, out)
                    self.done += 1
                    return True
            except (OSError, subprocess.TimeoutExpired) as e:
                err = str(e)
        tmp.unlink(missing_ok=True)
        self.failed[key] = err.strip() or "ffmpeg no generó imagen"
        self.errors = (self.errors + [{"clave": key, "error": self.failed[key], "ts": time.time()}])[-20:]
        log.warning("No se pudo generar la portada de %s: %s", key, self.failed[key])
        return False

    def status(self) -> dict:
        n = len(list(self.dir.glob("*.jpg"))) if self.dir.exists() else 0
        return {"ffmpeg": self.ffmpeg_path(), "disponible": self.available(), "en_cola": self.q.qsize(),
                "pendientes": len(self.pending), "generadas": self.done, "en_cache": n,
                "fallidas": len(self.failed), "errores": self.errors[-5:]}
