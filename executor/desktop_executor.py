"""Allowlisted local desktop executor."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.desktop_executor import DesktopExecutor

QUEUE = Path(__file__).resolve().parent / "queue"

def execute(request: dict) -> dict:
    payload = request.get("payload", request)
    action = str(payload.get("action") or request.get("type", "open_app")).lower()
    action = action.rsplit(".", 1)[-1]
    if action in {"click", "type_text"} and not request.get("confirmed", False):
        return {"status": "confirmation_required", "action": action}
    executor = DesktopExecutor()
    if action == "open_app":
        return executor.open_app(str(payload.get("target", "browser")))
    if action == "open_url":
        return executor.open_url(str(payload.get("url", "")))
    if action == "click":
        return executor.click(int(payload["x"]), int(payload["y"]))
    if action == "type_text":
        return executor.type_text(str(payload.get("text", "")))
    if action in {"screenshot", "take_screenshot"}:
        return executor.screenshot(payload.get("path"))
    return {"status": "blocked", "reason": "desktop_action_not_allowlisted", "action": action}


def process_queue() -> None:
    for path in QUEUE.glob("*.json"):
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            if request.get("type", "").startswith("desktop."):
                print(f"Desktop-Request: {execute(request)}", flush=True)
                path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Desktop-Request konnte nicht verarbeitet werden: {exc}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis Desktop Executor (Safe Mode)")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    QUEUE.mkdir(parents=True, exist_ok=True)
    print(f"Desktop-Executor bereit (Safe Mode), Queue: {QUEUE}", flush=True)
    try:
        while True:
            process_queue()
            time.sleep(max(0.25, args.interval))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
