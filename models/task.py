from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Task:
    id: str
    title: str
    owner: Optional[str]
    status: str
    priority: str
    due_date: Optional[datetime]
    blocked_by: list[str]
    description: Optional[str] = None
    list_id: Optional[str] = None
    item_id: Optional[str] = None
    url: Optional[str] = None
    raw_fields: dict[str, Any] = field(default_factory=dict)
