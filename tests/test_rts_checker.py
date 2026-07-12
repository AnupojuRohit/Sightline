import unittest
from unittest.mock import patch

from core.rts_checker import RTSChecker
from models.task import Task
from services.slack_oauth import SlackOAuthRequiredError


class FakeResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class RTSCheckerTests(unittest.TestCase):
    def test_check_task_uses_user_token_for_search(self) -> None:
        captured: dict[str, str | None] = {}

        def fake_urlopen(request, timeout=10):
            captured["authorization"] = request.get_header("Authorization")
            captured["url"] = request.full_url
            return FakeResponse('{"ok": true, "messages": {"matches": [{"text": "Task is done."}]}}')

        task = Task(
            id="1",
            title="Backend API",
            owner="Alice",
            status="In Progress",
            priority="High",
            due_date=None,
            blocked_by=[],
            raw_fields={"slack_user_id": "U123"},
        )

        with patch("core.rts_checker.require_user_token", return_value="xoxp-user-token"), patch(
            "core.rts_checker.urlopen", side_effect=fake_urlopen
        ):
            evidence = RTSChecker(client=object()).check_task(task, user_id="U123")

        self.assertEqual(captured["authorization"], "Bearer xoxp-user-token")
        self.assertIn("search.messages", captured["url"] or "")
        self.assertTrue(evidence)
        self.assertEqual(evidence[0].text, "Task is done.")

    def test_require_user_token_is_explicit_when_missing(self) -> None:
        with patch("services.slack_oauth.get_user_token", return_value=None):
            with self.assertRaises(SlackOAuthRequiredError) as context:
                from services.slack_oauth import require_user_token

                require_user_token("U123")

        self.assertIn("Complete /slack/oauth/authorize first", str(context.exception))

    def test_get_user_token_accepts_scoped_duplicate_entries(self) -> None:
        import services.slack_oauth as oauth

        original_tokens = dict(oauth._USER_TOKENS)
        try:
            oauth._USER_TOKENS.clear()
            oauth._USER_TOKENS["U123"] = "xoxp-user-token"
            oauth._USER_TOKENS["T123:U123"] = "xoxp-user-token"

            self.assertEqual(oauth.get_user_token(), "xoxp-user-token")
        finally:
            oauth._USER_TOKENS.clear()
            oauth._USER_TOKENS.update(original_tokens)

    def test_check_task_skips_rts_when_user_token_missing(self) -> None:
        task = Task(
            id="1",
            title="Backend API",
            owner="Alice",
            status="In Progress",
            priority="High",
            due_date=None,
            blocked_by=[],
            raw_fields={
                "rts": {
                    "query": "Backend API",
                    "text": "Task appears complete",
                    "confirms_done": True,
                }
            },
        )

        with patch("core.rts_checker.require_user_token", side_effect=SlackOAuthRequiredError("missing")):
            evidence = RTSChecker(client=object()).check_task(task, user_id="U123")

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].query, "Backend API")

    def test_check_task_skips_not_allowed_token_type_without_crashing(self) -> None:
        def fake_urlopen(request, timeout=10):
            return FakeResponse('{"ok": false, "error": "not_allowed_token_type"}')

        task = Task(
            id="1",
            title="Backend API",
            owner="Alice",
            status="In Progress",
            priority="High",
            due_date=None,
            blocked_by=[],
            raw_fields={},
        )

        with patch("core.rts_checker.require_user_token", return_value="xoxb-bot-token"), patch(
            "core.rts_checker.urlopen", side_effect=fake_urlopen
        ):
            evidence = RTSChecker(client=object()).check_task(task, user_id="U123")

        self.assertEqual(evidence, [])


if __name__ == "__main__":
    unittest.main()
