"""Bounded local Python executor process.

Arbitrary source execution is intentionally disabled. Requests are consumed
only when they are explicitly marked as blocked, so unsafe queue entries do
not remain stuck forever.
"""

import argparse
import json
import time
from pathlib import Path


def execute(request: dict) -> dict:
    return {"status": "blocked", "reason": "python_execution_requires_review"}


def process_queue(queue: Path) -> None:
    for path in queue.glob("*.json"):
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            if request.get("type") != "python.run_safe":
                continue
            result = execute(request)
            print(f"Python-Request {request.get('id', path.stem)}: {result}", flush=True)
            path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Python-Request konnte nicht verarbeitet werden: {exc}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis Python Executor (Safe Mode)")
    parser.add_argument("--once", action="store_true", help="Prüft die Queue einmal und beendet sich")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    queue = Path(__file__).resolve().parent / "queue"
    queue.mkdir(parents=True, exist_ok=True)
    print(f"Python-Executor bereit (Safe Mode), Queue: {queue}")
    if args.once:
        process_queue(queue)
        return 0
    try:
        while True:
            process_queue(queue)
            time.sleep(max(0.25, args.interval))
    except KeyboardInterrupt:
        print("Python-Executor beendet.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
