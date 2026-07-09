from dataclasses import dataclass


@dataclass
class Risk:
    title: str
    severity: str
    reason: str
    recommendation: str