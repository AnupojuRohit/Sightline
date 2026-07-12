import json
import logging
from typing import Any

from services.runtime_status import increment_stat, record_event
from services.slack_list_loader import SlackListLoader
from ui.blocks import build_update_result_blocks


def handle_update_task(ack: Any, body: dict[str, Any], client: Any, logger: logging.Logger) -> None:
    logger.info("update_action_entered")
    ack()

    payload = _action_payload(body)
    list_id = payload.get("list_id")
    item_id = payload.get("item_id")
    status = payload.get("status") or "Done"
    task_title = payload.get("task_title") or "this task"
    logger.info(
        "update_action_payload_parsed",
        extra={"list_id": list_id, "item_id": item_id, "status": status, "task_id": payload.get("task_id")},
    )
    record_event("Update clicked", f"Update requested for {task_title}", {"list_id": list_id, "item_id": item_id})

    if not list_id:
        logger.warning("update_task_missing_list_id")
        record_event("Update skipped", "Missing list id in button payload")
        _replace_message(client, body, "Update unavailable", "Sightline could not identify the Slack List.")
        return

    updated = SlackListLoader(client).update_task_status(str(list_id), _optional_str(item_id), str(status))
    if updated:
        logger.info("update_task_completed", extra={"list_id": list_id, "item_id": item_id})
        increment_stat("updates_applied")
        record_event("Update applied", f"Task updated to {status}", {"list_id": list_id, "item_id": item_id})
        _replace_message(client, body, "Task updated", f"{task_title} was updated to {status}.")
        return

    logger.warning("update_task_not_completed", extra={"list_id": list_id, "item_id": item_id})
    record_event("Update failed", "List update was not completed", {"list_id": list_id, "item_id": item_id})
    _replace_message(
        client,
        body,
        "Update not completed",
        "Sightline found the mismatch, but Slack List updates are not enabled or the item id was unavailable.",
    )


def handle_dismiss_task(ack: Any, body: dict[str, Any], client: Any, logger: logging.Logger) -> None:
    logger.info("dismiss_action_entered")
    ack()

    payload = _action_payload(body)
    task_title = payload.get("task_title") or "this task"
    logger.info(
        "dismiss_action_payload_parsed",
        extra={"list_id": payload.get("list_id"), "task_id": payload.get("task_id")},
    )
    record_event("Dismiss clicked", f"Dismiss requested for {task_title}", {"task_id": payload.get("task_id")})
    logger.info("mismatch_dismissed", extra={"task_id": payload.get("task_id"), "list_id": payload.get("list_id")})
    increment_stat("dismissals")
    record_event("Dismissed", f"Dismissed alert for {task_title}", {"task_id": payload.get("task_id")})
    _replace_message(client, body, "Dismissed", f"Sightline dismissed the stale-task alert for {task_title}.")


def _action_payload(body: dict[str, Any]) -> dict[str, Any]:
    actions = body.get("actions") or []
    if not actions:
        return {}

    value = actions[0].get("value")
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _replace_message(client: Any, body: dict[str, Any], title: str, message: str) -> None:
    logger = logging.getLogger(__name__)
    container = body.get("container") or {}
    channel = container.get("channel_id")
    ts = (body.get("message") or {}).get("ts") or container.get("message_ts")

    if not channel or not ts:
        logger.info("button_response_replace_skipped", extra={"reason": "missing_channel_or_ts", "title": title})
        return

    try:
        client.chat_update(
            channel=channel,
            ts=ts,
            text=title,
            blocks=build_update_result_blocks(title, message),
        )
        logger.info("button_response_replace_success", extra={"channel": channel, "ts": ts, "title": title})
    except Exception:
        logger.exception(
            "button_response_replace_failed",
            extra={"channel": channel, "ts": ts, "title": title},
        )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
