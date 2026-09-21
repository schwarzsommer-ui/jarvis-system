"""Central safety policy for bridge requests and live warnings."""

from __future__ import annotations

from typing import Any, Callable, Dict

BLOCKED_ACTIONS = {
    "file.delete", "file.overwrite", "file.write",
    "shell.execute", "execute_shell", "registry.write",
    "trade", "account.change", "send_message", "send_email",
}


def check_safety(action_type: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    normalized = str(action_type).strip().lower()
    blocked = normalized in BLOCKED_ACTIONS or any(
        marker in normalized for marker in (
            "delete", "overwrite", "shell", "registry", "trade", "account",
            "send_message", "send_email", "message", "email",
        )
    )
    return {
        "safe": not blocked,
        "blocked": blocked,
        "action_type": normalized,
        "reason": "dangerous_action_requires_explicit_review" if blocked else "",
    }


def send_safety_event(publisher: Callable[[str, Dict[str, Any]], Any], action_type: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    result = check_safety(action_type, payload)
    if result["blocked"]:
        publisher("safety.warning", result)
    return result
