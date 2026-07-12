from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from core.evidence_builder import EvidenceBuilder
from core.github_checker import GitHubChecker
from core.mismatch_engine import MismatchEngine
from core.rts_checker import RTSChecker
from models.analysis import Analysis
from models.mismatch import Mismatch
from models.task import Task
from services.analyzer import Analyzer
from services.runtime_status import record_event
from services.slack_list_loader import SlackListLoader

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanResult:
    list_id: str
    generated_at: str
    tasks: list[Task]
    mismatches: list[Mismatch]
    analysis: Analysis


def run_slack_list_scan(client: Any, list_id: str, user_id: str | None = None) -> ScanResult:
    logger.info(
        "scan_pipeline_entered list_id=%s user_id_present=%s",
        list_id,
        bool(user_id),
        extra={"list_id": list_id, "user_id_present": bool(user_id)},
    )
    record_event("Scan started", f"Scanning Slack List {list_id}", {"list_id": list_id})

    tasks = SlackListLoader(client).load_tasks(list_id)
    logger.info("scan_pipeline_list_loaded list_id=%s task_count=%s", list_id, len(tasks), extra={"list_id": list_id, "task_count": len(tasks)})
    record_event("Slack List loaded", f"Loaded {len(tasks)} task(s)", {"list_id": list_id})

    engine = MismatchEngine(
        EvidenceBuilder(
            github_checker=GitHubChecker(),
            rts_checker=RTSChecker(client),
        )
    )
    mismatches = engine.find_mismatches(tasks, user_id=user_id)
    logger.info(
        "scan_pipeline_engine_complete list_id=%s task_count=%s mismatch_count=%s",
        list_id,
        len(tasks),
        len(mismatches),
        extra={"list_id": list_id, "task_count": len(tasks), "mismatch_count": len(mismatches)},
    )
    record_event("Evidence built", f"Evaluated {len(tasks)} task(s)", {"list_id": list_id})
    record_event("Mismatch found", f"Found {len(mismatches)} mismatch(es)", {"list_id": list_id})

    analysis = Analyzer().analyze(tasks)
    logger.info(
        "scan_pipeline_complete list_id=%s health_score=%s risk_count=%s",
        list_id,
        analysis.health_score,
        len(analysis.risks),
        extra={"list_id": list_id, "health_score": analysis.health_score, "risk_count": len(analysis.risks)},
    )
    return ScanResult(
        list_id=list_id,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        tasks=tasks,
        mismatches=mismatches,
        analysis=analysis,
    )
