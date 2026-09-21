"""Safe, bounded synchronisation of the Cloudflare Telegram command queue."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional


class TelegramQueueSync:
    """Poll the remote queue and accept commands into the persistent local queue.

    Acceptance is deliberately separate from execution: every imported command is
    queued with ``approved=False`` and must go through the existing confirmation
    path before an action can run.
    """

    def __init__(
        self,
        task_queue: Any,
        audit: Any,
        publisher: Any = None,
        status_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.task_queue = task_queue
        self.audit = audit
        self.publisher = publisher
        self.status_callback = status_callback
        self.url = os.getenv("TELEGRAM_QUEUE_URL", "").strip().rstrip("/")
        self.token = os.getenv("TELEGRAM_QUEUE_TOKEN", "").strip()
        self.interval = self._bounded_int("TELEGRAM_QUEUE_POLL_SECONDS", 60, 15, 3600)
        self.max_items = self._bounded_int("TELEGRAM_QUEUE_BATCH_SIZE", 10, 1, 50)
        self.retries = 3
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def _bounded_int(name: str, default: int, lower: int, upper: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError:
            value = default
        return max(lower, min(value, upper))

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.token)

    def start(self) -> None:
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._thread = threading.Thread(target=self._run, name="telegram-queue-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self) -> None:
        self._poll_once()
        while not self._stop.wait(self.interval):
            self._poll_once()

    def poll_once(self) -> Dict[str, Any]:
        """Run one poll, useful for smoke tests and explicit operator sync."""
        return self._poll_once()

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = json.dumps(payload or {}).encode("utf-8") if method != "GET" else None
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "JarvisQueueSync/1.0",
            },
        )
        last_error: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(request, timeout=8) as response:
                    decoded = json.loads(response.read().decode("utf-8") or "{}")
                    return decoded if isinstance(decoded, dict) else {}
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = exc
                if isinstance(exc, urllib.error.HTTPError) and exc.code < 500:
                    break
                if attempt < self.retries - 1:
                    time.sleep(2 ** attempt)
        detail = f":{last_error.code}" if isinstance(last_error, urllib.error.HTTPError) else ""
        raise RuntimeError(f"queue_request_failed:{method}:{path}:{type(last_error).__name__}{detail}")

    @staticmethod
    def _items(response: Dict[str, Any]) -> list[Dict[str, Any]]:
        items = response.get("items", response.get("commands", response.get("queue", [])))
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    def _poll_once(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "accepted": 0}
        try:
            response = self._request("GET", f"/queue?limit={self.max_items}")
            items = self._items(response)
        except RuntimeError as exc:
            self._record("telegram_queue.poll_failed", {"error": str(exc)})
            return {"status": "error", "accepted": 0, "error": "queue_unavailable"}

        accepted = 0
        for item in items:
            remote_id = str(item.get("id") or item.get("queue_id") or item.get("update_id") or "").strip()
            if not remote_id:
                continue
            command = str(item.get("command") or item.get("text") or item.get("message") or "").strip()
            if not command or len(command) > 4000:
                self._record("telegram_queue.rejected", {"remote_id": remote_id, "reason": "invalid_command"})
                continue
            payload = {
                "command": command,
                "source": "telegram",
                "remote_id": remote_id,
                "confirmation_required": True,
                "approved": False,
            }
            task = self.task_queue.enqueue("telegram_command", payload)
            accepted += 1
            lease = item.get("lease_token") or item.get("lease") or response.get("lease_token")
            try:
                ack = {"id": remote_id, "task_id": task.task_id}
                if lease:
                    ack["lease_token"] = str(lease)
                self._request("POST", "/queue/ack", ack)
                self._record("telegram_queue.accepted", {"remote_id": remote_id, "task_id": task.task_id})
                self._send_status(remote_id, "accepted", task.task_id)
            except RuntimeError as exc:
                self._record("telegram_queue.ack_failed", {"remote_id": remote_id, "error": str(exc)})
                # The local durable queue contains the command; a later poll may
                # deliver it again, so do not execute it automatically.
        return {"status": "ok", "accepted": accepted, "received": len(items)}

    def _send_status(self, remote_id: str, status: str, task_id: str) -> None:
        try:
            self._request("POST", "/queue/status", {"id": remote_id, "status": status, "task_id": task_id})
        except RuntimeError:
            # Status delivery is best effort and must never prevent local acceptance.
            pass

    def _record(self, event: str, payload: Dict[str, Any]) -> None:
        self.audit.append(event, payload)
        if self.publisher is not None:
            self.publisher.publish(event, payload)
        if self.status_callback is not None:
            self.status_callback({"event": event, **payload})
