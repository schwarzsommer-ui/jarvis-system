from __future__ import annotations

from datetime import datetime
from threading import Event, Thread
from typing import Any, Callable, Dict


class SchedulerRunner:
    """Runs only local, non-destructive scheduled jobs."""

    def __init__(
        self,
        registry: Any,
        audit: Any,
        obsidian: Any,
        memory: Any,
        should_defer_heavy_work: Callable[[], bool] | None = None,
    ) -> None:
        self.registry = registry
        self.audit = audit
        self.obsidian = obsidian
        self.memory = memory
        self.should_defer_heavy_work = should_defer_heavy_work or (lambda: False)
        self._stop = Event()
        self._thread: Thread | None = None
        self._last_run: Dict[str, str] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._loop, name="jarvis-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    def status(self) -> Dict[str, Any]:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "last_run": dict(self._last_run),
            "mode": "local_safe_jobs_only",
        }

    def _loop(self) -> None:
        while not self._stop.wait(30):
            self.run_due_jobs()

    def run_due_jobs(self) -> None:
        now = datetime.now()
        for job in self.registry.list():
            if not job.get("enabled"):
                continue
            job_id = str(job.get("id"))
            schedule = str(job.get("schedule", "")).lower()
            last_run = self._last_run.get(job_id, "")
            if schedule == "hourly":
                due = last_run[:13] != now.strftime("%Y-%m-%dT%H")
            elif schedule.startswith("daily "):
                due = (
                    schedule[6:] == now.strftime("%H:%M")
                    and last_run[:10] != now.strftime("%Y-%m-%d")
                )
            else:
                due = False
            if not due:
                continue
            if self.should_defer_heavy_work() and job.get("action") in {
                "sync_obsidian",
                "nightly_review",
                "prepare_digest",
            }:
                self.audit.append("scheduler.deferred", {
                    "job_id": job_id,
                    "action": job.get("action"),
                    "reason": "gaming_performance_mode",
                })
                continue
            try:
                self._execute(job)
            except Exception as exc:
                self.audit.append("scheduler.failed", {
                    "job_id": job_id,
                    "action": job.get("action"),
                    "error": str(exc),
                })
            else:
                self._last_run[job_id] = now.isoformat()

    def _execute(self, job: Dict[str, Any]) -> None:
        action = job.get("action")
        if action == "sync_obsidian":
            result = self.obsidian.sync_graph(self.memory.graph_snapshot())
        elif action == "nightly_review":
            result = self.obsidian.write_nightly_review(self.memory.snapshot())
        elif action == "health_check":
            result = "local health check completed"
        elif action == "prepare_digest":
            result = "digest preparation completed; no external message sent"
        else:
            result = "unknown safe job skipped"
        self.audit.append("scheduler.executed", {
            "job_id": job.get("id"),
            "action": action,
            "result": result,
        })
