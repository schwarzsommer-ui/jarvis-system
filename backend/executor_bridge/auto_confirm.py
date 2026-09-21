"""Turns direct user commands into requests only for allowlisted safe actions."""

from __future__ import annotations

from typing import Any, Callable, Dict

from .allowlist import NEVER_AUTO_EXECUTE, is_allowed
from .execution_request import ExecutionRequest
from .safety import check_safety
from core.permission_registry import PermissionRegistry


def create_request(
    command: str,
    action_type: str,
    payload: Dict[str, Any] | None = None,
    publisher: Callable[[str, Dict[str, Any]], Any] | None = None,
    permission_registry: PermissionRegistry | None = None,
) -> ExecutionRequest:
    payload = dict(payload or {})
    safety = check_safety(action_type, payload)
    registry_granted = bool(
        permission_registry
        and permission_registry.is_granted(action_type, payload.get("target"))
    )
    # Grants supplement the safe allowlist, but can never weaken its safety
    # policy or the explicit per-action confirmation list.
    allowed = (
        safety["safe"]
        and action_type not in NEVER_AUTO_EXECUTE
        and (is_allowed(action_type, payload) or registry_granted)
    )
    if not allowed and publisher is not None:
        publisher("safety.warning", {
            "command": command,
            "action_type": action_type,
            "reason": safety["reason"] or "action_not_allowlisted",
            "blocked": True,
        })
    return ExecutionRequest(
        type=action_type,
        payload=payload,
        context={
            "command": command,
            "auto_confirmed": allowed,
            "allowlisted": allowed,
            "permission_granted": registry_granted,
            "requires_confirmation": not allowed,
            "safety": safety,
        },
        confirmed=allowed,
    )
