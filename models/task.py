from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Task:
    id: str
    title: str
    owner: Optional[str]
    status: str
    priority: str
    due_date: Optional[datetime]
    blocked_by: list[str]