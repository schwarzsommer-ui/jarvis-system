from backend.executor_bridge.allowlist import check, is_allowed
from backend.executor_bridge.auto_confirm import create_request


def test_allowlisted_action_is_auto_confirmed():
    assert check("desktop.open_app", {"target": "browser"})
    assert is_allowed("desktop.open_app", {"target": "browser"})
    request = create_request("Öffne den Browser", "desktop.open_app", {"target": "browser"})
    assert request.confirmed is True
    assert request.context["auto_confirmed"] is True


def test_unallowlisted_action_is_blocked():
    assert not is_allowed("python.execute", {"code": "print('x')"})
    request = create_request("Führe Code aus", "python.execute", {"code": "print('x')"})
    assert request.confirmed is False
    assert request.context["requires_confirmation"] is True


def test_blocked_request_can_publish_safety_warning():
    events = []
    request = create_request(
        "Sende E-Mail",
        "send_email",
        {},
        publisher=lambda event_type, payload: events.append((event_type, payload)),
    )
    assert request.confirmed is False
    assert events[0][0] == "safety.warning"


def test_executor_endpoint_persists_request(tmp_path, monkeypatch):
    from backend.api import create_app
    from backend.executor_bridge.request_store import RequestStore
    from fastapi.testclient import TestClient

    app = create_app()
    app.state.request_store = RequestStore(str(tmp_path))
    response = TestClient(app).post(
        "/executor",
        json={"command": "Öffne Browser", "type": "desktop.open_app", "payload": {"target": "browser"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert len(app.state.request_store.load_requests()) == 1
