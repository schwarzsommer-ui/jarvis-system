import json
from pathlib import Path
from typing import List
from .execution_request import ExecutionRequest

class RequestStore:
    def __init__(self, root: str = "executor/queue"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_request(self, request: ExecutionRequest) -> Path:
        path = self.root / f"{request.id}.json"
        path.write_text(json.dumps(request.to_dict(), indent=2), encoding="utf-8")
        return path

    def load_requests(self) -> List[dict]:
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.root.glob("*.json"))]

    def load_pending(self) -> List[dict]:
        return [
            request for request in self.load_requests()
            if request.get("status", "pending") == "pending"
        ]
