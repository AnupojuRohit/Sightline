from dataclasses import dataclass
from models.risk import Risk

@dataclass
class Analysis:
    health_score: int
    risks: list[Risk]
    total_tasks: int
    overdue_tasks: int
    blocked_tasks: int
    unassigned_tasks: int