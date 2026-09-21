"""Explicit, local desktop helpers for J.A.R.V.I.S.

These helpers only perform an action when called by a local user-controlled
process. They do not expose a network endpoint and never execute shell input.
"""

from __future__ import annotations

import os
import subprocess
import time
import webbrowser
from pathlib import Path

import pyautogui


def open_program(path: str) -> None:
    """Open a locally installed program by its executable path."""
    executable = Path(path).expanduser()
    if not executable.is_file():
        raise FileNotFoundError(f"Programm nicht gefunden: {executable}")
    subprocess.Popen([str(executable)], shell=False)


def click(x: int, y: int) -> None:
    """Move the pointer and click at a screen coordinate."""
    pyautogui.moveTo(int(x), int(y), duration=0.1)
    pyautogui.click()


def type_text(text: str) -> None:
    """Type text into the currently focused application."""
    pyautogui.write(str(text), interval=0.05)


def open_browser(url: str) -> None:
    """Open a URL in the user's default browser."""
    webbrowser.open(url, new=2)


def make_folder(path: str) -> Path:
    """Create a folder and return its resolved path."""
    folder = Path(path).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


def screenshot(path: str) -> Path:
    """Capture the visible screen and save it to a local path."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    image = pyautogui.screenshot()
    image.save(target)
    return target.resolve()


def wait(seconds: float = 1.0) -> None:
    """Pause between explicitly requested visible desktop actions."""
    time.sleep(max(0.0, float(seconds)))
