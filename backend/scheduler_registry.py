from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class SchedulerRegistry:
    def __init__(self, path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.path = path or root / "data" / "jarvis_scheduler.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({
                "jobs": [
                    {
                        "id": "morning-briefing",
                        "name": "Morgenbericht",
                        "schedule": "daily 08:00",
                        "action": "prepare_digest",
                        "enabled": False,
                        "requires_confirmation": False,
                    },
                    {
                        "id": "health-check",
                        "name": "Systemprüfung",
                        "schedule": "hourly",
                        "action": "health_check",
                        "enabled": False,
                        "requires_confirmation": False,
                    },
                    {
                        "id": "second-brain-sync",
                        "name": "Obsidian-Synchronisierung",
                        "schedule": "daily 20:00",
                        "action": "sync_obsidian",
                        "enabled": False,
                        "requires_confirmation": False,
                    },
                ],
                "policy": "local_plan_only_until_user_enables_job",
            })

    def _load(self) -> Dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"jobs": []}
        return value if isinstance(value, dict) else {"jobs": []}

    def _save(self, value: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> List[Dict[str, Any]]:
        return list(self._load().get("jobs", []))

    def set_enabled(self, job_id: str, enabled: bool) -> Dict[str, Any]:
        data = self._load()
        for job in data.get("jobs", []):
            if job.get("id") == job_id:
                job["enabled"] = bool(enabled)
                job["updated_at"] = datetime.now().isoformat()
                self._save(data)
                return job
        raise KeyError(f"Unknown scheduled job: {job_id}")
