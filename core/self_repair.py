import ast
import json
import os
from pathlib import Path
from datetime import datetime


class SelfRepair:
    """Runs explicit, non-destructive health checks for the local assistant."""

    def __init__(self, project_root=None, memory=None):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1])
        self.log_path = self.project_root / "core" / "improvement_log.json"
        self.memory = memory

    def record_issue(self, request, response):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        if self.log_path.exists():
            try:
                entries = json.loads(self.log_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                entries = []
        entries.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "request": request[:500],
            "response": response[:500],
        })
        self.log_path.write_text(
            json.dumps(entries[-100:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if self.memory is not None:
            self.memory.append("errors", {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "request": self._redact(request),
                "response": self._redact(response),
                "source": "self_repair",
            })

    @staticmethod
    def _redact(value):
        text = str(value or "")
        for marker in ("api_key", "token", "password", "secret"):
            text = text.replace(marker, f"{marker}=[REDACTED]")
        return text[:500]

    def run_improvement_cycle(self):
        result = self.run_check()
        if "fehlgeschlagen" in result:
            return result
        issue_count = 0
        if self.log_path.exists():
            try:
                issue_count = len(json.loads(self.log_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                issue_count = 0
        return (
            f"{result}\n"
            f"Verbesserungsprotokoll: {issue_count} beobachtete Fälle. "
            "Ich ändere keine Dateien automatisch ohne einen konkreten, "
            "prüfbaren Verbesserungsvorschlag."
        )

    def run_check(self):
        files = sorted(
            path for path in self.project_root.rglob("*.py")
            if "__pycache__" not in path.parts
        )
        failures = []
        for path in files:
            try:
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            except (OSError, SyntaxError) as exc:
                failures.append(f"{path.relative_to(self.project_root)}: {exc}")

        if failures:
            return (
                "Selbsttest fehlgeschlagen. Ich habe nichts verändert.\n"
                + "\n".join(f"- {failure}" for failure in failures)
            )
        return (
            f"Selbsttest erfolgreich: {len(files)} Python-Dateien geprüft. "
            "Es wurden keine Dateien verändert."
        )
