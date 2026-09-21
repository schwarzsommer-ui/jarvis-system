"""Small, local, auditable permission registry for command execution."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional


class PermissionRegistry:
    """Persist explicit action grants with optional target scoping.

    A grant is never a safety decision by itself; callers must still apply the
    normal supervisor/allowlist policy and the non-bypassable action set.
    """

    def __init__(self, path: Path | str | None = None, audit: Any = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.path = Path(path) if path else root / "data" / "jarvis_permissions.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = audit
        self._lock = RLock()

    @staticmethod
    def _action(action: str) -> str:
        value = str(action or "").strip().lower()
        if not value:
            raise ValueError("action is required")
        return value

    @staticmethod
    def _target(target: Any) -> Optional[str]:
        if target is None or str(target).strip() == "":
            return None
        return str(target).strip()

    def _read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "grants": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"version": 1, "grants": []}
        return data if isinstance(data, dict) and isinstance(data.get("grants"), list) else {"version": 1, "grants": []}

    def _write(self, data: Dict[str, Any]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(str(temporary), str(self.path))

    def _audit(self, event: str, payload: Dict[str, Any]) -> None:
        if self.audit is not None:
            self.audit.append(event, payload)

    def grant(self, action: str, target: Any = None, actor: str = "local") -> Dict[str, Any]:
        action_name, target_name = self._action(action), self._target(target)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            data = self._read()
            grants = [item for item in data["grants"] if not (
                item.get("action") == action_name and item.get("target") == target_name
            )]
            grant = {"action": action_name, "target": target_name, "granted_at": now, "actor": str(actor)[:120]}
            grants.append(grant)
            data["grants"] = grants
            self._write(data)
        self._audit("permission.granted", grant)
        return grant

    def revoke(self, action: str, target: Any = None, actor: str = "local") -> bool:
        action_name, target_name = self._action(action), self._target(target)
        with self._lock:
            data = self._read()
            kept = [item for item in data["grants"] if not (
                item.get("action") == action_name and item.get("target") == target_name
            )]
            changed = len(kept) != len(data["grants"])
            if changed:
                data["grants"] = kept
                self._write(data)
        if changed:
            self._audit("permission.revoked", {"action": action_name, "target": target_name, "actor": str(actor)[:120]})
        return changed

    def list(self) -> list[Dict[str, Any]]:
        with self._lock:
            return list(self._read()["grants"])

    def is_granted(self, action: str, target: Any = None) -> bool:
        action_name, target_name = self._action(action), self._target(target)
        with self._lock:
            return any(
                item.get("action") == action_name
                and (item.get("target") is None or item.get("target") == target_name)
                for item in self._read()["grants"]
            )
