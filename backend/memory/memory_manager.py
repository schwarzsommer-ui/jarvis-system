from pathlib import Path
from typing import Any, Dict, List
from backend.memory_store import MemoryStore

class MemoryManager:
    def __init__(self, root: str = "memory"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for category in ("knowledge", "history", "skills", "agents", "workflows", "logs", "versioning"):
            (self.root / category).mkdir(exist_ok=True)
        self.store = MemoryStore(str(self.root / "knowledge" / "memory.json"))

    def _save(self, category: str, value: Any) -> Any:
        result = self.store.append(category, value)
        (self.root / "history" / f"{category}.json").write_text(
            __import__("json").dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return result

    def save_command(self, command: str): return self._save("commands", command)
    def save_action_plan(self, plan: dict): return self._save("action_plans", plan)
    def save_executor_request(self, request: dict): return self._save("executor_requests", request)
    def save_result(self, result: dict): return self._save("results", result)
    def save_error(self, error: str): return self._save("errors", error)
    def save_improvement(self, note: str): return self._save("improvements", note)

    def query_memory(self, query: str) -> List[Dict[str, Any]]:
        needle = query.lower()
        results = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".txt", ".log"}:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if needle in content.lower():
                results.append({"path": str(path), "match": query})
        return results

    def export_memory(self) -> Dict[str, Any]:
        return self.store.snapshot()
