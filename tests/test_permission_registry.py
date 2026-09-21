from backend.executor_bridge.auto_confirm import create_request
from core.permission_registry import PermissionRegistry


def test_scoped_grant_is_persistent_and_revocable(tmp_path):
    path = tmp_path / "permissions.json"
    registry = PermissionRegistry(path)
    registry.grant("telegram.read", target="chat-42", actor="test")

    reloaded = PermissionRegistry(path)
    assert reloaded.is_granted("telegram.read", "chat-42")
    assert not reloaded.is_granted("telegram.read", "chat-99")
    assert reloaded.revoke("telegram.read", "chat-42", actor="test")
    assert not reloaded.is_granted("telegram.read", "chat-42")


def test_grant_can_confirm_safe_command_but_not_send_message(tmp_path):
    registry = PermissionRegistry(tmp_path / "permissions.json")
    registry.grant("telegram.read", target="chat-42")
    safe = create_request(
        "read",
        "telegram.read",
        {"target": "chat-42"},
        permission_registry=registry,
    )
    assert safe.confirmed is True
    registry.grant("send_message")
    dangerous = create_request(
        "send",
        "send_message",
        {"target": "chat-42"},
        permission_registry=registry,
    )
    assert dangerous.confirmed is False
    assert dangerous.context["requires_confirmation"] is True
