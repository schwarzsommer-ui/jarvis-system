import re
import subprocess
import time
import urllib.parse
import webbrowser

APPLICATIONS = {
    "editor": ("notepad.exe", "Editor"),
    "notepad": ("notepad.exe", "Editor"),
    "rechner": ("calc.exe", "Rechner"),
    "calculator": ("calc.exe", "Rechner"),
}

def open_application(app_name: str) -> str:
    """Öffnet eine Anwendung auf dem PC."""
    command = APPLICATIONS.get(str(app_name).strip().lower())
    if not command:
        return "Diese Anwendung ist aus Sicherheitsgründen nicht freigegeben."
    try:
        subprocess.Popen([command[0]], shell=False)
        return f"{command[1]} geöffnet."
    except Exception as e:
        return str(e)

def open_website(url: str) -> str:
    """Öffnet eine Webseite im Browser."""
    url = str(url).strip()
    if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.IGNORECASE) and not re.match(
        r"^https?://", url, re.IGNORECASE
    ):
        return "Nur sichere http(s)-Adressen dürfen geöffnet werden."
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://www.google.com/search?q={urllib.parse.quote(url)}"
    webbrowser.open(url)
    return f"Geöffnet: {url}"

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
