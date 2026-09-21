from backend.executor_bridge.execution_request import ExecutionRequest
from backend.executor_bridge.request_store import RequestStore
from backend.memory.memory_manager import MemoryManager
from executor.python_executor import execute

def test_request_store_roundtrip(tmp_path):
    store = RequestStore(str(tmp_path))
    request = ExecutionRequest("desktop", {"action": "open_app", "target": "browser"})
    store.save_request(request)
    assert store.load_requests()[0]["id"] == request.id

def test_memory_manager_query(tmp_path):
    memory = MemoryManager(str(tmp_path))
    memory.save_command("öffne Browser")
    assert memory.query_memory("browser")

def test_python_executor_disabled(monkeypatch):
    monkeypatch.delenv("JARVIS_EXECUTOR_ENABLED", raising=False)
    assert execute({"type": "python"})["status"] == "blocked"
