"""Safe workflow queue watcher.

Workflows are planning-only. This process records that a workflow was seen but
does not perform external actions.
"""

import json
import time
from pathlib import Path


QUEUE = Path(__file__).resolve().parent / "queue"


def main() -> int:
    QUEUE.mkdir(parents=True, exist_ok=True)
    print(f"Workflow-Executor bereit (nur Planung), Queue: {QUEUE}", flush=True)
    try:
        while True:
            for path in QUEUE.glob("*.json"):
                try:
                    request = json.loads(path.read_text(encoding="utf-8"))
                    if request.get("type") == "workflow.plan":
                        print(f"Workflow geplant: {request.get('id', path.stem)}", flush=True)
                        path.unlink(missing_ok=True)
                except (OSError, json.JSONDecodeError) as exc:
                    print(f"Workflow-Request konnte nicht verarbeitet werden: {exc}", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
