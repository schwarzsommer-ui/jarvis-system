"""Safe, auditable supervisor for local agent roles and dependencies."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


class AgentSupervisor:
    """Plan work, repair approved dependencies, and verify capability readiness.

    This supervisor never installs arbitrary packages or executes code from an
    external skill. Only capabilities declared in agent_supervisor.json can be
    repaired automatically.
    """

    def __init__(self):
        self.root = Path(__file__).resolve().parents[1]
        self.config = self._load_config()
        self.last_report = {}

    def _load_config(self):
        path = self.root / "config" / "agent_supervisor.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {
                "enabled": False,
                "auto_install_safe_dependencies": False,
                "max_install_seconds": 240,
                "max_retries": 0,
                "roles": [],
                "safe_capabilities": {},
            }

    @staticmethod
    def _imports_available(names):
        return all(importlib.util.find_spec(name) is not None for name in names)

    def _capability_for_request(self, request):
        text = str(request or "").lower()
        if re.search(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/", text):
            return "youtube_video"
        if any(word in text for word in ("youtube", "video", "browser", "webseite", "website")):
            return "browser"
        if any(word in text for word in ("ocr", "text im bild", "bildschirmtext", "sichtbar")):
            return "ocr"
        if any(word in text for word in ("klick", "maus", "tastatur", "desktop", "fenster")):
            return "desktop"
        if any(word in text for word in ("mikrofon", "sprache", "sprechen", "vorlesen")):
            return "voice"
        return ""

    def diagnose_request(self, request):
        """Return one canonical, non-installing capability diagnosis."""
        capability = self._capability_for_request(request)
        if not capability:
            return {
                "ok": True,
                "capability": "general",
                "required": [],
                "missing": [],
                "installed": [],
                "verified": True,
            }
        spec = self.config.get("safe_capabilities", {}).get(capability, {})
        packages = list(spec.get("packages", []))
        imports = list(spec.get("imports", []))
        missing = [
            package for package, import_name in zip(packages, imports)
            if importlib.util.find_spec(import_name) is None
        ]
        return {
            "ok": not missing,
            "capability": capability,
            "required": packages,
            "missing": missing,
            "installed": [],
            "verified": not missing,
            "repair_available": bool(
                self.config.get("enabled")
                and self.config.get("auto_install_safe_dependencies")
            ),
        }

    def _install(self, packages):
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            *packages,
        ]
        try:
            result = subprocess.run(
                command,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=int(self.config.get("max_install_seconds", 240)),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            return False, detail[-800:]
        return True, "Pakete erfolgreich installiert."

    def prepare(self, request):
        """Return an auditable plan and repair safe missing dependencies once."""
        capability = self._capability_for_request(request)
        roles = list(self.config.get("roles", []))
        report = {
            "ok": True,
            "capability": capability or "general",
            "roles": roles,
            "installed": False,
            "verified": True,
            "message": "Rollenplan erstellt; vorhandene Fähigkeiten sind einsatzbereit.",
        }
        if not capability:
            self.last_report = report
            return report
        spec = self.config.get("safe_capabilities", {}).get(capability, {})
        imports = list(spec.get("imports", []))
        packages = list(spec.get("packages", []))
        if self._imports_available(imports):
            self.last_report = report
            return report
        if not self.config.get("enabled") or not self.config.get("auto_install_safe_dependencies"):
            report.update(
                ok=False,
                verified=False,
                message=f"Fähigkeit {capability} benötigt fehlende Pakete; automatische Installation ist deaktiviert.",
            )
            self.last_report = report
            return report
        report["message"] = f"Supervisor installiert geprüfte Abhängigkeiten für {capability}."
        success, detail = self._install(packages)
        report["installed"] = success
        report["verified"] = success and self._imports_available(imports)
        report["ok"] = report["verified"]
        report["message"] = detail if report["ok"] else f"Fähigkeit {capability} konnte nicht verifiziert werden: {detail}"
        self.last_report = report
        return report

    def status(self):
        return dict(self.last_report)

    def readiness(self):
        """Report concrete dependency readiness without installing anything."""
        result = {}
        for capability, spec in self.config.get("safe_capabilities", {}).items():
            imports = list(spec.get("imports", []))
            available = self._imports_available(imports)
            result[capability] = {
                "status": "ready" if available else "missing",
                "imports": imports,
                "imports_available": available,
                "repair_available": bool(
                    self.config.get("enabled")
                    and self.config.get("auto_install_safe_dependencies")
                ),
            }
        return result

    def swarm_limits(self):
        return {
            "max_parallel_agents": int(self.config.get("max_parallel_agents", 1)),
            "max_queued_agents": int(self.config.get("max_queued_agents", 0)),
            "roles": list(self.config.get("roles", [])),
        }
