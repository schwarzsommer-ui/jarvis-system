from executor.desktop_executor import execute as execute_desktop

def run(request: dict) -> dict:
    results = []
    for action in request.get("payload", {}).get("actions", []):
        if action.get("type") == "desktop":
            results.append(execute_desktop(action))
        else:
            results.append({"status": "planned", "action": action})
    return {"status": "simulated", "results": results}
