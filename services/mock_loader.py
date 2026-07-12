from datetime import datetime, timedelta

from models.task import Task


def load_mock_tasks():
    now = datetime.now()
    return [
        Task(
            id="1",
            title="Backend API contract",
            owner="Maya",
            status="Todo",
            priority="High",
            due_date=now - timedelta(days=2),
            blocked_by=[],
            description="Finish backend API contract for https://github.com/acme/sightline/pull/142",
            raw_fields={
                "github": {
                    "kind": "pull_request",
                    "number": 142,
                    "owner": "acme",
                    "repo": "sightline",
                    "state": "closed",
                    "merged": True,
                    "url": "https://github.com/acme/sightline/pull/142",
                },
                "rts": {
                    "query": "PR #142",
                    "text": "PR #142 is merged and the backend API work is done.",
                    "confirms_done": True,
                },
            },
        ),
        Task(
            id="2",
            title="Billing empty state",
            owner="Alice",
            status="Blocked",
            priority="Medium",
            due_date=now + timedelta(days=2),
            blocked_by=["1"],
            description="Waiting on copy approval before final UI pass.",
            raw_fields={
                "rts": {
                    "query": "billing empty state",
                    "text": "Billing empty state copy is approved; design can move forward now.",
                    "confirms_done": False,
                },
            },
        ),
        Task(
            id="3",
            title="Invite flow QA",
            owner="Noah",
            status="In Progress",
            priority="High",
            due_date=now + timedelta(days=1),
            blocked_by=[],
            description="Validate invite flow after https://github.com/acme/sightline/pull/188",
            raw_fields={
                "github": {
                    "kind": "pull_request",
                    "number": 188,
                    "owner": "acme",
                    "repo": "sightline",
                    "state": "closed",
                    "merged": True,
                    "url": "https://github.com/acme/sightline/pull/188",
                },
                "rts": {
                    "query": "PR #188",
                    "text": "QA passed for invite flow after PR #188 merged.",
                    "confirms_done": True,
                },
            },
        ),
        Task(
            id="4",
            title="Webhook retry monitor",
            owner=None,
            status="In Progress",
            priority="High",
            due_date=now - timedelta(days=1),
            blocked_by=[],
            description="Add retry monitor to reduce silent webhook failures.",
            raw_fields={},
        ),
        Task(
            id="5",
            title="Docs quickstart refresh",
            owner="Ira",
            status="Done",
            priority="Low",
            due_date=now - timedelta(days=3),
            blocked_by=[],
            description="Refresh setup steps for the new Slack app scopes.",
            raw_fields={
                "rts": {
                    "query": "docs quickstart",
                    "text": "Docs quickstart refresh is done and published.",
                    "confirms_done": True,
                },
            },
        ),
    ]
