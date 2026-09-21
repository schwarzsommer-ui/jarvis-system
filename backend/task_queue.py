from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from typing import Any, Deque, Dict, List, Optional


@dataclass
class TaskRecord:
    task_id: str
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = 'queued'
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'kind': self.kind,
            'payload': dict(self.payload),
            'status': self.status,
            'created_at': self.created_at,
            'approved': self.approved,
        }


class TaskQueue:
    def __init__(self, maxsize: int = 128, storage_path: Optional[str] = None) -> None:
        self.maxsize = maxsize
        self.storage_path = Path(storage_path) if storage_path else (
            Path(__file__).resolve().parents[1] / 'data' / 'jarvis_tasks.json'
        )
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._items: Deque[TaskRecord] = deque(self._load(), maxlen=maxsize)

    def _load(self) -> List[TaskRecord]:
        if not self.storage_path.exists():
            return []
        try:
            raw = json.loads(self.storage_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
        return [
            TaskRecord(
                task_id=str(item.get('task_id', '')),
                kind=str(item.get('kind', 'generic')),
                payload=dict(item.get('payload') or {}),
                status=str(item.get('status', 'queued')),
                created_at=str(item.get('created_at') or datetime.now(timezone.utc).isoformat()),
                approved=bool(item.get('approved', False)),
            )
            for item in raw if isinstance(item, dict) and item.get('task_id')
        ] if isinstance(raw, list) else []

    def _save(self) -> None:
        self.storage_path.write_text(
            json.dumps([item.to_dict() for item in self._items], ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def enqueue(self, kind: str, payload: Optional[Dict[str, Any]] = None) -> TaskRecord:
        with self._lock:
            task = TaskRecord(
                task_id=f'task-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")}',
                kind=kind,
                payload=dict(payload or {}),
            )
            self._items.append(task)
            self._save()
            return task

    def pending(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [task.to_dict() for task in self._items if task.status in {'queued', 'pending_confirmation'}]

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return next((task for task in self._items if task.task_id == task_id), None)

    def set_status(self, task_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            task = self.get(task_id)
            if task is None:
                raise KeyError(f'Unknown task: {task_id}')
            task.status = str(status)
            if result is not None:
                task.payload['result'] = dict(result)
            self._save()
            return task.to_dict()

    def next(self) -> Optional[TaskRecord]:
        with self._lock:
            for task in self._items:
                if task.status == 'queued':
                    return task
        return None

    def pop_next(self) -> Optional[TaskRecord]:
        task = self.next()
        if task is None:
            return None
        with self._lock:
            task.status = 'running'
            self._save()
            return task

    def complete(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            for task in self._items:
                if task.task_id == task_id:
                    task.status = 'completed'
                    task.payload['result'] = result or {}
                    self._save()
                    return task.to_dict()
        raise KeyError(f'Unknown task: {task_id}')

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [task.to_dict() for task in self._items]
