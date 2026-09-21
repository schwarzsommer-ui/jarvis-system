def plan(action: str, path: str) -> dict:
    return {"workflow": "file_automation", "status": "pending_confirmation", "action": action, "path": path}
