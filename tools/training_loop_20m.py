import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8787"
COMMANDS = (
    "Öffne TradingView und zeige BTC/USDT",
    "Suche die aktuellen Bitcoin Nachrichten",
    "Öffne den XAUUSD Chart",
    "Öffne den DXY Chart",
    "Öffne den Browser",
    "Prüfe den aktiven Bildschirm",
    "Zeige mir die verfügbaren Tools",
    "Öffne Notepad",
    "Öffne TradingView, suche BTC/USDT und lies den zugänglichen Chat",
)


def main():
    deadline = datetime.now() + timedelta(minutes=20)
    cycles = 0
    plans_checked = 0
    errors = []
    session = requests.Session()

    while datetime.now() < deadline:
        try:
            response = session.post(f"{BASE_URL}/learning/train", json={}, timeout=30)
            if response.status_code != 200:
                errors.append(f"learning/train HTTP {response.status_code}")
            for command in COMMANDS:
                response = session.post(
                    f"{BASE_URL}/plan",
                    json={"prompt": command},
                    timeout=30,
                )
                if response.status_code == 200 and response.json().get("status") in {
                    "ready",
                    "needs_clarification",
                }:
                    plans_checked += 1
                else:
                    errors.append(f"plan HTTP {response.status_code}")
            cycles += 1
        except requests.RequestException as exc:
            errors.append(type(exc).__name__)
        time.sleep(30)

    report = {
        "completed_at": datetime.now().isoformat(),
        "duration_minutes": 20,
        "cycles": cycles,
        "plans_checked": plans_checked,
        "errors": errors[-20:],
    }
    destination = ROOT / "SecondBrain" / "knowledge" / "training_session_20m.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
