"""Explicit, allowlisted installation of optional local Jarvis skills."""

import json
from pathlib import Path

from .agent_supervisor import AgentSupervisor


class SkillManager:
    IMPORTS = {
        "playwright": "playwright",
        "pywinauto": "pywinauto",
        "pyautogui": "pyautogui",
        "pytesseract": "pytesseract",
        "Pillow": "PIL",
        "psutil": "psutil",
        "numpy": "numpy",
        "nemo_retriever": "nemo_retriever",
        "sounddevice": "sounddevice",
        "pyperclip": "pyperclip",
    }
    PACKAGES = {
        "sprache": "SpeechRecognition",
        "mikrofon": "SpeechRecognition",
        "audio": "pygame",
        "zwischenablage": "pyperclip",
        "bilder": "Pillow",
        "tts": "edge-tts",
        "desktop": "pyautogui",
        "maus": "pyautogui",
        "klicks": "pyautogui",
        "browser": "playwright",
        "webautomation": "playwright",
        "ui": "pywinauto",
        "windowsui": "pywinauto",
        "ocr": "pytesseract",
        "vision": "Pillow",
        "system": "psutil",
        "monitoring": "psutil",
        "sound": "sounddevice",
        "realtime": "numpy",
        "genai": "google-genai",
        "api": "fastapi",
        "webserver": "uvicorn",
        "planner": "numpy",
        "memory": "numpy",
        "autogen": "numpy",
        "liveworkflow": "playwright",
        "desktopagent": "pyautogui",
        "browser_forms": "playwright",
        "form_fill": "playwright",
        "workflow": "playwright",
        "taskautomation": "playwright",
        "winui": "pywinauto",
        "windowsdesktop": "pywinauto",
        "appautomation": "pywinauto",
        "desktopapps": "pywinauto",
    }

    @classmethod
    def describe_skill_catalog(cls):
        catalog = {
            "desktop_control": "pyautogui + pyperclip + pywinauto für Maus, Tastatur, Genauigkeit und UI-Klicks.",
            "browser_automation": "playwright für echte Browser-Interaktion und Seitenlogik.",
            "browser_forms": "Formularfüllung, Klicks und Submit-Flows mit verifizierter Ausführung im Browser.",
            "windows_ui": "pywinauto für echte Windows-Anwendungs-UI mit sichtbaren Buttons, Feldern und Fenstern.",
            "vision": "Pillow und OCR für Screenshot-/Bildverarbeitung.",
            "monitoring": "psutil + sounddevice + numpy für System- und Live-Status.",
            "cloud_integration": "google-genai + fastapi + uvicorn für lokale KI-/Service-Bridges.",
            "task_planning": "Planner-Layer für echte Multi-Step-Aufgaben mit Verifikation nach jedem Schritt.",
            "desktop_agent": "Maus, Tastatur, Fenster und lokale Operationen in einem verifizierten Workflow.",
            "nemo_retriever": "NeMo Retriever für lokale Dokumentindizes und evidenzbasierte Second-Brain-Suche.",
        }
        return catalog

    @classmethod
    def capability_report(cls):
        catalog = cls.describe_skill_catalog()
        return {
            "free_local_stack": list(catalog.keys()),
            "notes": "Lokale KI-, Browser- und Windows-Desktop-Automation ohne teure Remote-Desktop-Tools; alles bleibt auf dem Rechner.",
            "priority": [
                "desktop_agent",
                "windows_ui",
                "browser_automation",
                "browser_forms",
                "task_planning",
                "nemo_retriever",
                "monitoring",
                "vision",
                "cloud_integration",
            ],
        }

    def list_available_skill_names(self):
        return sorted(set(self.PACKAGES.keys()))

    def preflight(self, request: str, install_missing: bool = False):
        """Compatibility wrapper around the single non-installing diagnosis path."""
        result = AgentSupervisor().diagnose_request(request)
        result["install_requested"] = bool(install_missing)
        return result

    @classmethod
    def community_catalog(cls):
        path = Path(__file__).resolve().parents[1] / "config" / "community_catalogs.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {
                "sources": [],
                "safe_import_policy": {
                    "automatic_install": False,
                    "note": "Community-Katalog nicht verfügbar.",
                },
                "mapped_capabilities": {},
            }

    def install_requested(self, request):
        lowered = request.lower()
        if (
            "community" in lowered and ("katalog" in lowered or "skill" in lowered)
        ) or any(marker in lowered for marker in (
            "community-katalog", "openclaw katalog", "claude katalog",
            "externe skills", "skill katalog",
        )):
            catalog = self.community_catalog()
            lines = ["Community-Kataloge sind verfügbar, aber nicht automatisch installiert."]
            for source in catalog.get("sources", []):
                lines.append(f"- {source['name']}: {source['purpose']}")
            lines.append(
                "Aktivierung erfolgt nur einzeln nach Quellcode-, Lizenz- und "
                "Sicherheitsprüfung."
            )
            return "\n".join(lines)
        if any(keyword in lowered for keyword in ("skill", "skills", "tools", "was kannst du", "toolliste", "liste")):
            catalog = self.describe_skill_catalog()
            items = "\n".join(f"- {name}: {desc}" for name, desc in catalog.items())
            return "Verfügbare starke lokale Skills:\n" + items

        matches = [
            (label, package)
            for label, package in self.PACKAGES.items()
            if label in lowered
        ]
        if not matches:
            allowed = ", ".join(sorted(set(self.PACKAGES.values())))
            return (
                "Dafür ist kein freigegebenes Paket erkannt. "
                f"Installierbar sind nur: {allowed}."
            )

        selected = []
        for _, package in matches:
            if package not in selected:
                selected.append(package)

        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pip", "install", *selected],
                check=False,
                capture_output=True,
                text=True,
                timeout=240,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"Installation von {selected} fehlgeschlagen: {exc}"
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            return f"Installation von {selected} fehlgeschlagen: {detail[-500:]}"
        return f"Skills installiert: {', '.join(selected)}. Starte Jarvis bei Bedarf neu."
