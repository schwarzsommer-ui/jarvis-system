"""Bounded, real Windows desktop actions for the local Jarvis backend."""

from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Dict

import pyautogui


class DesktopExecutor:
    """Execute only explicit, reversible desktop actions."""

    def open_app(self, target: str) -> Dict[str, Any]:
        value = target.strip()
        apps = {
            "browser": "https://www.google.com",
            "chrome": "https://www.google.com",
            "edge": "msedge",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
        }
        command = apps.get(value.lower())
        if not command:
            raise ValueError("App nicht in der Allowlist")
        if command.startswith("http"):
            webbrowser.open(command)
        else:
            subprocess.Popen([command], shell=False)
        return {"ok": True, "status": "executed", "action": "open_app", "target": value}

    def open_url(self, url: str) -> Dict[str, Any]:
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError("Nur HTTP(S)-URLs sind erlaubt")
        webbrowser.open(url)
        return {"ok": True, "status": "executed", "action": "open_url", "url": url}

    def screenshot(self, path: str | None = None) -> Dict[str, Any]:
        destination = Path(path or os.path.join(os.getcwd(), "SecondBrain", "screenshots", "screen.png"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        pyautogui.screenshot().save(destination)
        return {"ok": True, "status": "executed", "action": "screenshot", "path": str(destination)}

    def click(self, x: int, y: int) -> Dict[str, Any]:
        pyautogui.click(x=x, y=y)
        return {"ok": True, "status": "executed", "action": "click", "x": x, "y": y}

    def type_text(self, text: str) -> Dict[str, Any]:
        pyautogui.write(text, interval=0.03)
        return {"ok": True, "status": "executed", "action": "type_text", "length": len(text)}

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "desktop": "live",
            "enabled": True,
            "confirmation_required": ["click", "type_text"],
        }
