import unittest
from datetime import datetime

from core.mismatch_engine import MismatchEngine
from models.mismatch import EvidenceBundle, GitHubReference, GitHubState, RTSEvidence
from models.task import Task


class StaticEvidenceBuilder:
    def __init__(self, evidence: EvidenceBundle):
        self.evidence = evidence

    def build(self, task: Task) -> EvidenceBundle:
        return self.evidence


class MismatchEngineTests(unittest.TestCase):
    def test_merged_pr_with_active_status_is_stale(self) -> None:
        task = self._task(status="In Progress")
        evidence = EvidenceBundle(
            github=[
                GitHubState(
                    reference=GitHubReference(kind="pull_request", number=142),
                    state="closed",
                    merged=True,
                )
            ]
        )

        mismatches = MismatchEngine(StaticEvidenceBuilder(evidence)).find_mismatches([task])

        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0].recommended_status, "Done")

    def test_done_status_remains_silent(self) -> None:
        task = self._task(status="Done")
        evidence = EvidenceBundle(
            rts=[RTSEvidence(query="Backend API", text="Backend API is done.", confirms_done=True)]
        )

        mismatches = MismatchEngine(StaticEvidenceBuilder(evidence)).find_mismatches([task])

        self.assertEqual(mismatches, [])

    def _task(self, status: str) -> Task:
        return Task(
            id="1",
            title="Backend API",
            owner="Alice",
            status=status,
            priority="High",
            due_date=datetime.now(),
            blocked_by=[],
        )


if __name__ == "__main__":
    unittest.main()
