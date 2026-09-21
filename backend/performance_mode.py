"""Low-overhead gaming detection and background-work policy."""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict

import psutil


DEFAULT_GAME_PROCESSES = {
    "eldenring.exe",
    "fortniteclient-win64-shipping.exe",
    "gta5.exe",
    "leagueclient.exe",
    "overwatch.exe",
    "rocketleague.exe",
    "valorant-win64-shipping.exe",
    "cs2.exe",
}


class PerformanceMode:
    """Detect games without polling aggressively and expose a safe policy."""

    def __init__(self) -> None:
        configured = os.getenv("JARVIS_GAME_PROCESSES", "")
        names = {item.strip().lower() for item in configured.split(",") if item.strip()}
        self.game_processes = names or DEFAULT_GAME_PROCESSES
        self._lock = threading.Lock()
        self._snapshot: Dict[str, Any] = {
            "gaming": False,
            "game_process": None,
            "checked_at": None,
            "performance_mode": False,
            "mode": "auto",
        }
        self._last_check = 0.0
        self._manual_mode: bool | None = None

    def set_mode(self, mode: str) -> Dict[str, Any]:
        """Set resource policy to automatic detection, forced on, or forced off."""
        normalized = str(mode or "auto").strip().lower()
        if normalized not in {"auto", "on", "off"}:
            raise ValueError("mode must be auto, on, or off")
        with self._lock:
            self._manual_mode = {"auto": None, "on": True, "off": False}[normalized]
            self._refresh()
            self._last_check = time.monotonic()
            return dict(self._snapshot)

    def snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            if now - self._last_check >= 10:
                self._refresh()
                self._last_check = now
            return dict(self._snapshot)

    def _refresh(self) -> None:
        found = None
        for process in psutil.process_iter(["name"]):
            try:
                name = (process.info.get("name") or "").lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if name in self.game_processes:
                found = name
                break
        detected_gaming = found is not None
        performance_mode = (
            detected_gaming if self._manual_mode is None else self._manual_mode
        )
        self._snapshot = {
            "gaming": found is not None,
            "game_process": found,
            "checked_at": time.time(),
            "performance_mode": performance_mode,
            "mode": (
                "auto"
                if self._manual_mode is None
                else ("on" if self._manual_mode else "off")
            ),
            "policy": "defer_heavy_background_work" if performance_mode else "normal",
            "tracked_processes": sorted(self.game_processes),
        }

    def should_defer_heavy_work(self) -> bool:
        return bool(self.snapshot()["performance_mode"])
