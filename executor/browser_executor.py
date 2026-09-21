"""Allowlisted local browser executor."""

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

QUEUE = Path(__file__).resolve().parent / "queue"


def execute(page, request: dict) -> dict:
    action = request.get("type")
    payload = request.get("payload") or {}
    if action in {"browser.open", "browser.navigate"}:
        url = str(payload.get("url", "")).strip()
        if not url or not url.startswith(("http://", "https://")):
            return {"status": "blocked", "reason": "invalid_browser_url"}
        page.goto(url, wait_until="domcontentloaded")
        return {"status": "completed", "action": action, "url": url}
    if action == "browser.screenshot":
        target = Path(str(payload.get("path", "memory/browser-screenshot.png")))
        target.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target))
        return {"status": "completed", "path": str(target)}
    return {"status": "blocked", "reason": "browser_action_not_allowlisted"}


def process_queue(page) -> None:
    for path in QUEUE.glob("*.json"):
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            if request.get("type", "").startswith("browser."):
                print(f"Browser-Request: {execute(page, request)}", flush=True)
                path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Browser-Request konnte nicht verarbeitet werden: {exc}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis Browser Executor")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    QUEUE.mkdir(parents=True, exist_ok=True)
    print(f"Browser-Executor bereit, Queue: {QUEUE}", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            while True:
                process_queue(page)
                time.sleep(max(0.25, args.interval))
        except KeyboardInterrupt:
            return 0
        finally:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
