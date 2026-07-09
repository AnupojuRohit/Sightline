import logging

from core.evidence_builder import EvidenceBuilder
from models.mismatch import EvidenceBundle, GitHubState, Mismatch, RTSEvidence
from models.task import Task

logger = logging.getLogger(__name__)

DONE_STATUSES = {"done", "complete", "completed", "closed", "merged"}
ACTIVE_STATUSES = {"todo", "to do", "in progress", "blocked", "active", "open"}


class MismatchEngine:
    def __init__(self, evidence_builder: EvidenceBuilder):
        self.evidence_builder = evidence_builder

    def find_mismatches(self, tasks: list[Task]) -> list[Mismatch]:
        mismatches: list[Mismatch] = []

        for task in tasks:
            evidence = self.evidence_builder.build(task)
            task_mismatches = self._evaluate_task(task, evidence)
            mismatches.extend(task_mismatches)

            logger.info(
                "mismatch_result",
                extra={
                    "task_id": task.id,
                    "status": task.status,
                    "mismatch_count": len(task_mismatches),
                },
            )

        return mismatches

    def _evaluate_task(self, task: Task, evidence: EvidenceBundle) -> list[Mismatch]:
        mismatches: list[Mismatch] = []

        for github_state in evidence.github:
            mismatch = self._evaluate_github(task, evidence, github_state)
            if mismatch:
                mismatches.append(mismatch)

        for rts_evidence in evidence.rts:
            mismatch = self._evaluate_rts(task, evidence, rts_evidence)
            if mismatch:
                mismatches.append(mismatch)

        return mismatches

    def _evaluate_github(
        self,
        task: Task,
        evidence: EvidenceBundle,
        github_state: GitHubState,
    ) -> Mismatch | None:
        if self._is_done(task.status):
            return None

        reference = github_state.reference
        label = f"{reference.kind} #{reference.number}"

        if github_state.merged:
            return Mismatch(
                task=task,
                reason=f"GitHub {label} is merged, but the List status is {task.status}.",
                recommended_status="Done",
                evidence=evidence,
            )

        if github_state.state == "closed" and self._is_active(task.status):
            return Mismatch(
                task=task,
                reason=f"GitHub {label} is closed, but the List status is {task.status}.",
                recommended_status="Done",
                evidence=evidence,
            )

        return None

    def _evaluate_rts(
        self,
        task: Task,
        evidence: EvidenceBundle,
        rts_evidence: RTSEvidence,
    ) -> Mismatch | None:
        if self._is_done(task.status) or not rts_evidence.confirms_done:
            return None

        return Mismatch(
            task=task,
            reason=f"Slack evidence suggests this is done, but the List status is {task.status}.",
            recommended_status="Done",
            evidence=evidence,
        )

    def _is_done(self, status: str) -> bool:
        return status.strip().lower() in DONE_STATUSES

    def _is_active(self, status: str) -> bool:
        return status.strip().lower() in ACTIVE_STATUSES or not self._is_done(status)
