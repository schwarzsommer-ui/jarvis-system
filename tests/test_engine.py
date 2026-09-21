from fastapi.testclient import TestClient
from backend.api import create_app


def test_engine_creates_allowlisted_executor_request():
    client = TestClient(create_app())
    response = client.post("/executor", json={
        "command": "Öffne den Browser",
        "type": "desktop.open_app",
        "payload": {"target": "browser"},
    })
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_engine_blocks_unknown_executor_request():
    client = TestClient(create_app())
    response = client.post("/executor", json={
        "command": "Führe Shell aus",
        "type": "execute_shell",
        "payload": {"command": "whoami"},
    })
    assert response.json()["status"] == "blocked"
