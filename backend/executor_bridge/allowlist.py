"""Explicit action allowlist for the local executor bridge."""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlparse

ALLOWLIST = {
    # Browser actions are still constrained by URL and executor policies.
    "browser.open",
    "browser.navigate",
    "browser.click_safe",
    "browser.fill_safe",
    "browser.scroll",
    "browser.screenshot",
    "browser.download",
    "browser.extract_text",
    "browser.extract_links",
    "browser.read_dom",
    # Reversible, local desktop actions.
    "desktop.move_window",
    "desktop.focus_window",
    "desktop.type",
    "desktop.hotkey_safe",
    "desktop.click_safe",
    "desktop.scroll",
    "desktop.screenshot",
    # Bounded data-only Python operations.
    "python.run_safe",
    "python.analyze_data",
    "python.calculate",
    "python.transform_text",
    "python.simulate",
    # Planning and analysis workflows only.
    "workflow.plan",
    "workflow.run_safe",
    "workflow.news_scan",
    "workflow.trading_analysis_safe",
    "workflow.file_read_safe",
    "workflow.browser_flow_safe",
    "workflow.self_improvement",
    # Local memory and observability.
    "memory.save",
    "memory.update",
    "memory.tag",
    "memory.search",
    "log.info",
    "log.warn",
    "log.error",
    "live.event",
    "agent.status",
    "agent.update",
    "agent.think",
    "agent.plan",
    "agent.report",
    # Existing local compatibility action.
    "desktop.open_app",
    "browser.open_url",
}

SAFE_ACTIONS = ALLOWLIST

NEVER_AUTO_EXECUTE = {
    "python.execute",
    "desktop.type_text",
    "desktop.click",
    "file.delete",
    "file.move",
    "send_message",
    "send_email",
    "trade",
}

ACTION_ALIASES = {
    "browser.open_url": "browser.open",
    "desktop.type_text": "desktop.type",
    "python.execute": "python.run_safe",
}


def is_allowed(action_type: str, payload: Dict[str, Any] | None = None) -> bool:
    action_type = str(action_type).strip().lower()
    original_action_type = action_type
    if action_type in NEVER_AUTO_EXECUTE:
        return False
    action_type = ACTION_ALIASES.get(action_type, action_type)
    if action_type not in SAFE_ACTIONS:
        return False
    if original_action_type in {
        "browser.open_url",
        "browser.open",
        "browser.navigate",
        "browser.download",
    }:
        parsed = urlparse(str((payload or {}).get("url", "")))
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    return True


def check(action_type: str, payload: Dict[str, Any] | None = None) -> bool:
    """Compatibility name for callers that only need an allowlist decision."""
    return is_allowed(action_type, payload)
