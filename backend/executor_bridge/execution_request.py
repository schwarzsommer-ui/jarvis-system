from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

@dataclass
class ExecutionRequest:
    type: str
    payload: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confirmed: bool = False
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
