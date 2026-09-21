from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from core.memory import JarvisMemory


class MemoryStore:
    def __init__(self, storage_path: Optional[str] = None) -> None:
        self._memory = JarvisMemory(filepath=storage_path)

    def set(self, key: str, value: Any) -> Any:
        return self._memory.set(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._memory.get(key, default)

    def delete(self, key: str) -> None:
        self._memory.delete(key)

    def append(self, key: str, value: Any) -> List[Any]:
        return self._memory.append(key, value)

    def snapshot(self) -> Dict[str, Any]:
        return self._memory.snapshot()
