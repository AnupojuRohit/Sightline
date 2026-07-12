import json
import logging
from html import escape
from typing import Any

from models.analysis import Analysis
from models.mismatch import Mismatch

logger = logging.getLogger(__name__)

UPDATE_TASK_ACTION_ID = "sightline_update_task"
DISMISS_TASK_ACTION_ID = "sightline_dismiss_task"


def build_analysis_blocks(analysis: Analysis, report: str):
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Sightline Analysis",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Health Score*\n{analysis.health_score}/100",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Total Tasks*\n{analysis.total_tasks}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Overdue*\n{analysis.overdue_tasks}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Blocked*\n{analysis.blocked_tasks}",
                },
            ],
        },
        {
            "type": "divider",
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": report[:2900],
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Analyze Again",
                    },
                    "action_id": "analyze_again",
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Generate Plan",
                    },
                    "action_id": "generate_plan",
                },
            ],
        },
    ]


def build_mismatch_blocks(mismatch: Mismatch, explanation: str | None = None) -> list[dict[str, Any]]:
    task = mismatch.task
    evidence_lines = _evidence_lines(mismatch)
    payload = _button_payload(mismatch)

    context_text = (
        f"*Task:* {_mrkdwn(task.title)}\n"
        f"*Current status:* `{_mrkdwn(task.status)}`\n"
        f"*Recommended:* `{_mrkdwn(mismatch.recommended_status)}`"
    )

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Potentially Stale Task",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": context_text,
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "*Severity*\nHigh",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Action*\nUpdate to {_mrkdwn(mismatch.recommended_status)}",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Why Sightline flagged this*\n{_mrkdwn(mismatch.reason)}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Evidence*\n" + "\n".join(evidence_lines),
            },
        },
    ]

    if explanation:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": _mrkdwn(explanation[:250]),
                    }
                ],
            }
        )

    blocks.extend(
        [
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {
                            "type": "plain_text",
                            "text": "Update Task",
                            "emoji": True,
                        },
                        "action_id": UPDATE_TASK_ACTION_ID,
                        "value": payload,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Dismiss",
                            "emoji": True,
                        },
                        "action_id": DISMISS_TASK_ACTION_ID,
                        "value": payload,
                    },
                ],
            },
        ]
    )

    logger.info(
        "block_kit_mismatch_card_built",
        extra={"list_id": task.list_id, "task_id": task.id, "block_count": len(blocks)},
    )
    return blocks


def build_update_result_blocks(title: str, message: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{_mrkdwn(title)}*\n{_mrkdwn(message)}",
            },
        }
    ]


def build_home_blocks() -> list[dict[str, Any]]:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Sightline",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Open a Slack List. Sightline stays silent unless it finds a stale task.",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Evidence comes from Slack Lists, GitHub, and Slack search. Rules decide; AI only explains.",
                }
            ],
        },
    ]


def _evidence_lines(mismatch: Mismatch) -> list[str]:
    lines: list[str] = []

    for github_state in mismatch.evidence.github[:2]:
        reference = github_state.reference
        state = "merged" if github_state.merged else github_state.state
        label = f"{reference.kind.replace('_', ' ').title()} #{reference.number}"
        if reference.repo:
            label = f"{reference.repo} {label}"
        lines.append(f"- {_mrkdwn(label)} is `{_mrkdwn(state)}`")

    for rts in mismatch.evidence.rts[:2]:
        text = rts.text.replace("\n", " ").strip()
        if len(text) > 120:
            text = text[:117] + "..."
        lines.append(f"- Slack: {_mrkdwn(text)}")

    if not lines:
        lines.append("- Slack List status conflicts with available source-of-truth evidence.")

    return lines[:4]


def _button_payload(mismatch: Mismatch) -> str:
    task = mismatch.task
    return json.dumps(
        {
            "list_id": task.list_id,
            "item_id": task.item_id,
            "task_id": task.id,
            "task_title": task.title,
            "status": mismatch.recommended_status,
        },
        separators=(",", ":"),
    )[:1900]


def _mrkdwn(value: object) -> str:
    return escape(str(value), quote=False)
