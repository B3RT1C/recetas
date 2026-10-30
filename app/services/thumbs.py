"""Card covers: grab one frame from each local video with ffmpeg, in a background thread.

Thumbnails are cached as media/thumbs/<key>.jpg (key = shortcode, or r<id> for manual recipes).
Since v2.1.2 the *automatic* frame is only the fallback when no original post thumbnail exists
(see ``RecipeService._cover``). Frames that are black or near-black (fade-ins, title cards) are
rejected by measuring the mean luma of a 16x16 grey downscale; later timestamps are tried in turn.
User-chosen frames (cover_source=frame) are cached as media/thumbs/<key>__t<ms>.jpg.
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
AUTO_TIMES = (1.0, 2.0, 3.0, 5.0, 8.0, 0.5, 0.0)  # ~1 s first; later ones skip fade-ins
BLACK_LUMA = 24  # mean Y (0-255) below this counts as a black / near-black frame


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

    def frame_cover(self, key: str, video: Optional[Path], t: float) -> Optional[str]:
        """URL of a user-chosen frame at ``t`` seconds (generated on demand, cached)."""
        if video is None or not video.exists():
            return None
        p = self.frame_path(key, t)
        if not p.exists() and not self.render_frame(video, t, p):
            return None
        return f"/media/thumbs/{p.name}?v={int(p.stat().st_mtime)}"

    def frame_path(self, key: str, t: float) -> Path:
        base = self.path_for(key)
        return base.with_name(f"{base.stem}__t{int(round(t * 1000))}.jpg")

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

    def _grab(self, exe: str, video: Path, ss: float, out: Path, width: int = WIDTH) -> str:
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{ss:.3f}", "-i", str(video),
               "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(out)]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            return str(e)
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return ""
        return r.stderr.decode(errors="replace")[-300:].strip() or "ffmpeg no generó imagen"

    def luma(self, image: Path) -> Optional[float]:
        """Mean luma (0-255) of an image, via a 16x16 grey downscale."""
        exe = self.ffmpeg_path()
        if not exe:
            return None
        try:
            r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-i", str(image), "-vf",
                                "scale=16:16,format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return sum(r.stdout) / len(r.stdout) if r.returncode == 0 and r.stdout else None

    def render_frame(self, video: Path, t: float, out: Path, width: int = WIDTH) -> bool:
        """One frame at exactly ``t`` seconds (user choice: no black check)."""
        exe = self.ffmpeg_path()
        if not exe:
            return False
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".part.jpg")
        err = self._grab(exe, video, max(0.0, t), tmp, width)
        if err:
            tmp.unlink(missing_ok=True)
            return False
        os.replace(tmp, out)
        return True

    def extract(self, key: str, video: Path, times: tuple[float, ...] = AUTO_TIMES) -> bool:
        """Automatic cover: first non-black frame from ``times`` (falls back to the brightest one)."""
        exe = self.ffmpeg_path()
        if not exe:
            return False
        self.dir.mkdir(parents=True, exist_ok=True)
        out = self.path_for(key)
        err, best, best_luma = "", None, -1.0
        for n, ss in enumerate(times):
            tmp = out.with_name(f"{out.stem}.part{n}.jpg")
            e = self._grab(exe, video, ss, tmp)
            if e:  # usually: clip shorter than ss
                err = err or e
                tmp.unlink(missing_ok=True)
                continue
            y = self.luma(tmp)
            if y is None or y >= BLACK_LUMA:
                os.replace(tmp, out)
                break
            log.debug("portada %s: fotograma negro en %.1fs (luma %.1f)", key, ss, y)
            if y > best_luma:
                if best:
                    best.unlink(missing_ok=True)
                best, best_luma = tmp, y
            else:
                tmp.unlink(missing_ok=True)
        else:
            if best is None:
                self.failed[key] = err or "ffmpeg no generó imagen"
                self.errors = (self.errors + [{"clave": key, "error": self.failed[key], "ts": time.time()}])[-20:]
                log.warning("No se pudo generar la portada de %s: %s", key, self.failed[key])
                return False
            os.replace(best, out)  # every frame was dark: keep the least dark one
            best = None
        if best:
            best.unlink(missing_ok=True)
        self.done += 1
        return True

    def status(self) -> dict:
        n = len([p for p in self.dir.glob("*.jpg") if "__t" not in p.stem]) if self.dir.exists() else 0
        return {"ffmpeg": self.ffmpeg_path(), "disponible": self.available(), "en_cola": self.q.qsize(),
                "pendientes": len(self.pending), "generadas": self.done, "en_cache": n,
                "fallidas": len(self.failed), "errores": self.errors[-5:]}
