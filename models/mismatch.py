from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from models.task import Task


@dataclass(frozen=True)
class GitHubReference:
    kind: str
    number: int
    owner: Optional[str] = None
    repo: Optional[str] = None
    url: Optional[str] = None


@dataclass(frozen=True)
class GitHubState:
    reference: GitHubReference
    state: str
    merged: bool = False
    title: Optional[str] = None
    updated_at: Optional[datetime] = None
    url: Optional[str] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class RTSEvidence:
    query: str
    text: str
    url: Optional[str] = None
    user: Optional[str] = None
    timestamp: Optional[str] = None
    confirms_done: bool = False


@dataclass(frozen=True)
class EvidenceBundle:
    github: list[GitHubState] = field(default_factory=list)
    rts: list[RTSEvidence] = field(default_factory=list)


@dataclass(frozen=True)
class Mismatch:
    task: Task
    reason: str
    recommended_status: str
    evidence: EvidenceBundle
