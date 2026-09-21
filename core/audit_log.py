from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class AuditLog:
    def __init__(
        self,
        path: Path | None = None,
        sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        self.path = path or root / "data" / "jarvis_audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sink = sink

    def set_sink(self, sink: Optional[Callable[[Dict[str, Any]], Any]]) -> None:
        self.sink = sink

    @staticmethod
    def _redact(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return re.sub(
            r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]\s*\S+",
            r"\1=[REDACTED]",
            value,
        )[:12000]

    def append(self, event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "payload": {key: self._redact(value) for key, value in payload.items()},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self.sink is not None:
            try:
                self.sink(record)
            except (OSError, ValueError, TypeError):
                pass
        return record

    def recent(self, limit: int = 50) -> list[Dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        records = []
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if isinstance(record, dict):
                records.append(record)
        return records
