"""Bounded local project actions for the Jarvis bridge.

This module deliberately exposes operations instead of a general-purpose shell.
It is local-only, workspace-bound, secret-aware, time-limited, and auditable.
"""

import hashlib
import difflib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


class ProjectRunner:
    MAX_FILE_BYTES = 1_000_000
    MAX_OUTPUT_CHARS = 12_000
    MAX_TIMEOUT = 120
    SECRET_NAMES = {".env", ".env.local", ".env.production", ".env.development"}
    SECRET_PARTS = (".pem", ".key", "credentials", "secret", "token")
    COMMANDS = {
        "python_syntax": [os.environ.get("PYTHON", "py"), "-m", "compileall", "-q", "."],
        "python_tests": [os.environ.get("PYTHON", "py"), "-m", "pytest", "-q"],
        "npm_test": ["npm.cmd", "test", "--", "--runInBand"],
        "npm_build": ["npm.cmd", "run", "build"],
    }

    def __init__(self, workspace=None):
        root = Path(workspace or os.getenv("JARVIS_WORKSPACE", Path.cwd())).resolve()
        if not root.is_dir():
            raise ValueError("JARVIS_WORKSPACE muss ein vorhandener Ordner sein.")
        self.workspace = root
        self.audit_path = root / ".jarvis" / "audit.jsonl"
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def _audit(self, event, **data):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **data,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _safe_path(self, relative_path, must_exist=False):
        value = str(relative_path or "").strip().replace("\\", "/")
        candidate = (self.workspace / value).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError("Der Pfad liegt außerhalb des Projekt-Workspace.") from exc
        if candidate.name.lower() in self.SECRET_NAMES or any(
            part in candidate.name.lower() for part in self.SECRET_PARTS
        ):
            raise ValueError("Geheime oder sensible Dateien sind für den Runner gesperrt.")
        if must_exist and not candidate.is_file():
            raise ValueError("Die angegebene Datei existiert nicht.")
        return candidate

    def read_file(self, relative_path):
        path = self._safe_path(relative_path, must_exist=True)
        if path.stat().st_size > self.MAX_FILE_BYTES:
            raise ValueError("Die Datei ist für eine Vorschau zu groß.")
        content = path.read_text(encoding="utf-8")
        self._audit("read_file", path=str(path.relative_to(self.workspace)))
        return {"path": str(path.relative_to(self.workspace)), "content": content}

    def plan_write(self, relative_path, content):
        path = self._safe_path(relative_path)
        value = str(content)
        if len(value.encode("utf-8")) > self.MAX_FILE_BYTES:
            raise ValueError("Die Datei überschreitet das Größenlimit.")
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        plan = {
            "operation": "write_file",
            "path": str(path.relative_to(self.workspace)),
            "exists": path.exists(),
            "changed": previous != value,
            "old_sha256": hashlib.sha256(previous.encode("utf-8")).hexdigest(),
            "new_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            "old_bytes": len(previous.encode("utf-8")),
            "new_bytes": len(value.encode("utf-8")),
        }
        self._audit("plan_write", **plan)
        return plan

    def execute_write(self, relative_path, content, confirmed=False, expected_old_sha256=None):
        plan = self.plan_write(relative_path, content)
        if not confirmed:
            return {"ok": False, "error_code": "confirmation_required", "plan": plan}
        if expected_old_sha256 and plan["old_sha256"] != expected_old_sha256:
            raise ValueError("Die Datei wurde seit der Vorschau verändert.")
        path = self._safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8", newline="")
        # A successful write call is not proof that the requested bytes reached
        # disk (network folders and interrupted writes can report success).
        written = path.read_text(encoding="utf-8")
        written_sha256 = hashlib.sha256(written.encode("utf-8")).hexdigest()
        if written_sha256 != plan["new_sha256"]:
            self._audit(
                "write_verify_failed",
                path=plan["path"],
                expected_sha256=plan["new_sha256"],
                actual_sha256=written_sha256,
            )
            return {
                "ok": False,
                "error_code": "write_verification_failed",
                "path": plan["path"],
                "message": "Datei wurde geschrieben, die anschließende Prüfung ist aber fehlgeschlagen.",
                "plan": plan,
            }
        self._audit("write_file", path=plan["path"], bytes=plan["new_bytes"])
        return {
            "ok": True,
            "path": plan["path"],
            "message": "Datei geschrieben und verifiziert.",
            "sha256": written_sha256,
            "plan": plan,
        }

    def plan_repair(self, relative_path, content, reason=""):
        path = self._safe_path(relative_path, must_exist=True)
        previous = path.read_text(encoding="utf-8")
        value = str(content)
        if len(value.encode("utf-8")) > self.MAX_FILE_BYTES:
            raise ValueError("Die Reparatur überschreitet das Größenlimit.")
        diff = "".join(difflib.unified_diff(
            previous.splitlines(keepends=True),
            value.splitlines(keepends=True),
            fromfile=str(path.relative_to(self.workspace)),
            tofile=str(path.relative_to(self.workspace)),
        ))
        plan = self.plan_write(relative_path, value)
        plan.update({
            "operation": "repair_file",
            "reason": str(reason)[:500],
            "diff": diff[-self.MAX_OUTPUT_CHARS:],
        })
        self._audit("plan_repair", path=plan["path"], reason=plan["reason"])
        return plan

    def execute_repair(
        self, relative_path, content, confirmed=False, expected_old_sha256=None,
        reason=""
    ):
        plan = self.plan_repair(relative_path, content, reason)
        if not confirmed:
            return {"ok": False, "error_code": "confirmation_required", "plan": plan}
        result = self.execute_write(
            relative_path,
            content,
            confirmed=True,
            expected_old_sha256=expected_old_sha256 or plan["old_sha256"],
        )
        result["repair"] = {
            "reason": plan["reason"],
            "diff": plan["diff"],
        }
        self._audit("repair_applied", path=plan["path"], reason=plan["reason"])
        return result

    def run_command(self, command_name, confirmed=False, timeout=120):
        if command_name not in self.COMMANDS:
            raise ValueError("Dieser Befehl ist nicht freigegeben.")
        command = self.COMMANDS[command_name]
        try:
            limit = min(max(int(timeout), 1), self.MAX_TIMEOUT)
        except (TypeError, ValueError) as exc:
            raise ValueError("Ungültiges Timeout.") from exc
        plan = {"operation": "run_command", "command": command_name, "timeout": limit}
        if not confirmed:
            return {"ok": False, "error_code": "confirmation_required", "plan": plan}
        started = time.monotonic()
        self._audit("command_start", **plan)
        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace,
                shell=False,
                capture_output=True,
                text=True,
                timeout=limit,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self._audit("command_timeout", **plan)
            partial = "\n".join(
                part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part or "")
                for part in (exc.stdout, exc.stderr)
            ).strip()
            return {
                "ok": False,
                "error_code": "timeout",
                "message": f"Befehl nach {limit} Sekunden abgebrochen.",
                "output": partial[-self.MAX_OUTPUT_CHARS:],
            }
        except FileNotFoundError as exc:
            self._audit("command_failed", error_code="executable_not_found", **plan)
            return {
                "ok": False,
                "error_code": "executable_not_found",
                "message": f"Ausführbares Programm nicht gefunden: {exc.filename or command[0]}",
                "output": "",
            }
        except OSError as exc:
            self._audit("command_failed", error_code="os_error", detail=str(exc), **plan)
            return {
                "ok": False,
                "error_code": "os_error",
                "message": f"Befehl konnte nicht gestartet werden: {exc}",
                "output": "",
            }
        output = (completed.stdout + "\n" + completed.stderr).strip()
        result = {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "command": command_name,
            "duration_seconds": round(time.monotonic() - started, 2),
            "output": output[-self.MAX_OUTPUT_CHARS:],
        }
        self._audit("command_finish", **result)
        return result

    def status(self):
        return {
            "enabled": True,
            "workspace": str(self.workspace),
            "controls": [
                "workspace_boundary",
                "secret_exclusion",
                "confirmation_before_write_or_command",
                "command_allowlist",
                "timeout",
                "audit_log",
            ],
        }
