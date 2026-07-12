import unittest

from core.github_checker import GitHubChecker
from models.mismatch import GitHubReference, GitHubState
from models.task import Task


class FakeLiveProvider:
    def check_reference(self, reference: GitHubReference) -> GitHubState:
        return GitHubState(
            reference=reference,
            state="closed",
            merged=True,
            title="Live PR",
            url=reference.url,
        )


class GitHubCheckerTests(unittest.TestCase):
    def test_live_provider_wins_over_embedded_metadata(self) -> None:
        task = Task(
            id="1",
            title="Backend API",
            owner="Alice",
            status="In Progress",
            priority="High",
            due_date=None,
            blocked_by=[],
            description="See https://github.com/acme/widget/pull/42",
            raw_fields={
                "github": {
                    "kind": "pull_request",
                    "number": 42,
                    "owner": "acme",
                    "repo": "widget",
                    "state": "open",
                    "merged": False,
                }
            },
        )

        states = GitHubChecker(state_provider=FakeLiveProvider()).check_task(task)

        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].state, "closed")
        self.assertTrue(states[0].merged)
        self.assertEqual(states[0].title, "Live PR")

    def test_metadata_is_used_when_live_lookup_returns_unknown(self) -> None:
        class UnknownProvider:
            def check_reference(self, reference: GitHubReference) -> GitHubState:
                return GitHubState(reference=reference, state="unknown", reason="offline")

        task = Task(
            id="1",
            title="Backend API",
            owner="Alice",
            status="In Progress",
            priority="High",
            due_date=None,
            blocked_by=[],
            description="See https://github.com/acme/widget/issues/7",
            raw_fields={
                "github": {
                    "kind": "issue",
                    "number": 7,
                    "owner": "acme",
                    "repo": "widget",
                    "state": "closed",
                }
            },
        )

        states = GitHubChecker(state_provider=UnknownProvider()).check_task(task)

        self.assertEqual(states[0].state, "closed")


if __name__ == "__main__":
    unittest.main()
