import os
import subprocess
import webbrowser
import time

from core.agent_tools import DesktopControls

def open_application(app_name: str) -> str:
    """Öffnet eine Anwendung auf dem PC."""
    return DesktopControls().open_application(app_name)["message"]

def open_website(url: str) -> str:
    """Öffnet eine Webseite im Browser."""
    return DesktopControls().open_url(url)["message"]

def type_text(text: str) -> str:
    """Tippt Text auf der Tastatur."""
    try:
        import pyautogui
    except ImportError:
        return "Tippen ist nicht verfügbar: pyautogui ist nicht installiert."
    time.sleep(0.5)
    pyautogui.write(text, interval=0.02)
    pyautogui.press("enter")
    return f"Getippt: {text}"
