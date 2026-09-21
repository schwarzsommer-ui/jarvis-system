def test_memory_manager_persists_and_searches(tmp_path):
    from backend.memory.memory_manager import MemoryManager
    memory = MemoryManager(str(tmp_path))
    memory.save_result({"message": "Browser geöffnet"})
    assert memory.query_memory("browser")
