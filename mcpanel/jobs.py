"""Tâches de fond (téléchargements, resets) avec suivi de progression."""
from __future__ import annotations

import threading
import time
import traceback
import uuid

from .bus import BUS

_MAX_KEEP = 40


class Job:
    __slots__ = ("id", "kind", "target", "status", "progress", "message", "error", "created", "ended", "result")

    def __init__(self, kind: str, target: str | None = None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.target = target
        self.status = "pending"
        self.progress = 0.0
        self.message = ""
        self.error: str | None = None
        self.result = None
        self.created = time.time()
        self.ended: float | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "target": self.target,
            "status": self.status,
            "progress": round(self.progress, 3),
            "message": self.message,
            "error": self.error,
            "result": self.result,
            "created": self.created,
            "ended": self.ended,
            "elapsed": round((self.ended or time.time()) - self.created, 2),
        }


class JobRunner:
    """Une file par cible: les actions d'un même serveur ne se marchent pas dessus."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def _queue_lock(self, target: str) -> threading.Lock:
        with self._lock:
            if target not in self._locks:
                self._locks[target] = threading.Lock()
            return self._locks[target]

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def recent(self, limit: int = 10) -> list[dict]:
        with self._lock:
            ids = self._order[-limit:]
            return [self._jobs[i].as_dict() for i in ids if i in self._jobs]

    def submit(self, kind: str, fn, target: str = "global", serialize: bool = True) -> Job:
        job = Job(kind, target)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > _MAX_KEEP:
                old = self._order.pop(0)
                self._jobs.pop(old, None)

        def report(message: str = "", progress: float | None = None) -> None:
            if message:
                job.message = message
            if progress is not None:
                job.progress = max(0.0, min(1.0, progress))
            BUS.emit("job", job.as_dict())

        def runner() -> None:
            lock = self._queue_lock(target) if serialize else None
            if lock:
                if not lock.acquire(timeout=180):
                    job.status = "error"
                    job.error = "Une autre opération sur %s est déjà en cours." % target
                    job.ended = time.time()
                    BUS.emit("job", job.as_dict())
                    return
            try:
                job.status = "running"
                report("Démarrage...", 0.0)
                job.result = fn(report)
                job.status = "done"
                job.progress = 1.0
                if not job.message or job.message == "Démarrage...":
                    job.message = "Terminé"
            except Exception as exc:  # noqa: BLE001 - on remonte tout à l'UI
                job.status = "error"
                job.error = str(exc) or exc.__class__.__name__
                job.message = job.error
                BUS.emit(
                    "log",
                    {"server": target, "line": "[panel] %s: %s" % (kind, job.error), "lvl": "error", "t": time.time()},
                )
                traceback.print_exc()
            finally:
                job.ended = time.time()
                if lock:
                    lock.release()
                BUS.emit("job", job.as_dict())

        threading.Thread(target=runner, name="job-%s-%s" % (kind, job.id), daemon=True).start()
        BUS.emit("job", job.as_dict())
        return job


RUNNER = JobRunner()
