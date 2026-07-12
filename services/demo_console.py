from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from core.evidence_builder import EvidenceBuilder
from core.github_checker import GitHubChecker
from core.mismatch_engine import MismatchEngine
from core.rts_checker import RTSChecker
from models.mismatch import EvidenceBundle, Mismatch
from models.task import Task
from services.analyzer import Analyzer
from services.mock_loader import load_mock_tasks
from services.scan_pipeline import ScanResult
from ui.blocks import build_mismatch_blocks


DEMO_LIST_ID = "L-DEMO-SIGHTLINE"


def build_demo_console_payload() -> dict[str, Any]:
    tasks = load_mock_tasks()
    evidence_builder = EvidenceBuilder(
        github_checker=GitHubChecker(),
        rts_checker=RTSChecker(),
    )
    mismatches = MismatchEngine(evidence_builder).find_mismatches(tasks)
    analysis = Analyzer().analyze(tasks)

    return build_scan_console_payload(
        ScanResult(
            list_id=DEMO_LIST_ID,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            tasks=tasks,
            mismatches=mismatches,
            analysis=analysis,
        )
    )


def build_scan_console_payload(result: ScanResult) -> dict[str, Any]:
    mismatch_by_task = {mismatch.task.id: mismatch for mismatch in result.mismatches}
    status_counts = Counter(task.status for task in result.tasks)
    stale_task_ids = {mismatch.task.id for mismatch in result.mismatches}

    return {
        "listId": result.list_id,
        "generatedAt": result.generated_at,
        "summary": {
            "healthScore": result.analysis.health_score,
            "totalTasks": result.analysis.total_tasks,
            "staleTasks": len(stale_task_ids),
            "blockedTasks": result.analysis.blocked_tasks,
            "overdueTasks": result.analysis.overdue_tasks,
            "unassignedTasks": result.analysis.unassigned_tasks,
            "automationReadiness": _automation_readiness(result.tasks, result.mismatches),
        },
        "statusCounts": dict(status_counts),
        "tasks": [_serialize_task(task, mismatch_by_task.get(task.id)) for task in result.tasks],
        "mismatches": [_serialize_mismatch(mismatch) for mismatch in result.mismatches],
        "risks": [
            {
                "title": risk.title,
                "severity": risk.severity,
                "reason": risk.reason,
                "recommendation": risk.recommendation,
            }
            for risk in result.analysis.risks
        ],
        "timeline": _timeline(result.mismatches),
        "alertPreview": _alert_preview(result.mismatches[0]) if result.mismatches else None,
    }


def _automation_readiness(tasks: list[Task], mismatches: list[Mismatch]) -> int:
    if not tasks:
        return 0

    evidence_rich = sum(
        1
        for mismatch in mismatches
        if mismatch.evidence.github or mismatch.evidence.rts
    )
    return min(100, round((evidence_rich / len(tasks)) * 100 + 55))


def _serialize_task(task: Task, mismatch: Mismatch | None) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "owner": task.owner or "Unassigned",
        "status": task.status,
        "recommendedStatus": mismatch.recommended_status if mismatch else task.status,
        "priority": task.priority,
        "dueDate": task.due_date.date().isoformat() if task.due_date else None,
        "blockedBy": task.blocked_by,
        "description": task.description,
        "isStale": mismatch is not None,
        "reason": mismatch.reason if mismatch else None,
        "evidence": _serialize_evidence(mismatch.evidence if mismatch else EvidenceBundle()),
    }


def _serialize_mismatch(mismatch: Mismatch) -> dict[str, Any]:
    return {
        "taskId": mismatch.task.id,
        "taskTitle": mismatch.task.title,
        "currentStatus": mismatch.task.status,
        "recommendedStatus": mismatch.recommended_status,
        "reason": mismatch.reason,
        "evidence": _serialize_evidence(mismatch.evidence),
    }


def _serialize_evidence(evidence: EvidenceBundle) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for github_state in evidence.github:
        reference = github_state.reference
        repo = f"{reference.owner}/{reference.repo}" if reference.owner and reference.repo else reference.repo
        state = "merged" if github_state.merged else github_state.state
        rows.append(
            {
                "source": "GitHub",
                "label": f"{repo or 'repository'} #{reference.number}",
                "detail": f"{reference.kind.replace('_', ' ')} is {state}",
                "url": github_state.url or reference.url,
            }
        )

    for rts_evidence in evidence.rts:
        rows.append(
            {
                "source": "Slack",
                "label": rts_evidence.query,
                "detail": rts_evidence.text,
                "url": rts_evidence.url,
            }
        )

    return rows


def _timeline(mismatches: list[Mismatch]) -> list[dict[str, str]]:
    if not mismatches:
        return [
            {
                "step": "Scan complete",
                "detail": "No stale tasks were found in the current demo list.",
            }
        ]

    first = mismatches[0]
    task = first.task
    evidence = _serialize_evidence(first.evidence)
    timeline = [
        {
            "step": "Slack List opened",
            "detail": f"Sightline reads '{task.title}' with status '{task.status}'.",
        }
    ]

    for row in evidence[:3]:
        timeline.append(
            {
                "step": f"{row['source']} evidence",
                "detail": row["detail"],
            }
        )

    timeline.append(
        {
            "step": "Recommendation ready",
            "detail": f"Update '{task.title}' to '{first.recommended_status}'.",
        }
    )
    return timeline


def _alert_preview(mismatch: Mismatch) -> dict[str, Any]:
    evidence = _serialize_evidence(mismatch.evidence)
    return {
        "title": "Potentially Stale Task",
        "taskTitle": mismatch.task.title,
        "currentStatus": mismatch.task.status,
        "recommendedStatus": mismatch.recommended_status,
        "reason": mismatch.reason,
        "evidence": evidence[:4],
        "blocks": build_mismatch_blocks(mismatch),
    }
