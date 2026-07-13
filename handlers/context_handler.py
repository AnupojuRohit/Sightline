import logging
from typing import Any

from services.gemini_service import GeminiService
from services.runtime_status import increment_stat, record_event
from services.scan_pipeline import run_slack_list_scan
from ui.blocks import build_mismatch_blocks

logger = logging.getLogger(__name__)

LIST_ENTITY_TYPE = "slack#/types/list_id"
_POSTED_MISMATCH_KEYS: set[str] = set()


def handle_context_change(event: dict[str, Any], client: Any, logger: logging.Logger) -> None:
    _print_app_context_changed_event(event)
    logger.info("app_context_changed_entered")
    increment_stat("context_events")
    record_event("Context changed", "Slack app_context_changed received")

    list_id = _extract_list_id(event)
    if not list_id:
        logger.info("app_context_ignored_no_list")
        record_event("Context ignored", "No Slack List entity in event payload")
        return
    logger.info("app_context_list_id_extracted list_id=%s", list_id, extra={"list_id": list_id})
    record_event("List identified", f"List id: {list_id}")

    channel = _resolve_response_channel(event)
    if not channel:
        logger.warning("app_context_no_response_channel", extra={"list_id": list_id})
        record_event("Context ignored", "No response channel resolved", {"list_id": list_id})
        return
    logger.info("app_context_response_channel_resolved list_id=%s channel=%s", list_id, channel, extra={"list_id": list_id, "channel": channel})

    try:
        result = run_slack_list_scan(client, list_id, user_id=_resolve_user_id(event))
    except Exception:
        logger.exception("app_context_scan_failed", extra={"list_id": list_id})
        record_event("Scan failed", "Slack List scan failed", {"list_id": list_id})
        return
    tasks = result.tasks
    if not tasks:
        logger.info("slack_list_no_tasks", extra={"list_id": list_id})
        return

    mismatches = result.mismatches

    if mismatches:
        increment_stat("mismatches_found", len(mismatches))
    record_event("Engine ran", f"Found {len(mismatches)} mismatch(es)", {"list_id": list_id})

    if not mismatches:
        logger.info("sightline_silent_no_mismatch", extra={"list_id": list_id, "task_count": len(tasks)})
        record_event("Silent", "No mismatch detected", {"list_id": list_id})
        return

    mismatch = mismatches[0]
    dedupe_key = _dedupe_key(list_id, mismatch.task.id, mismatch.reason, mismatch.recommended_status)
    if dedupe_key in _POSTED_MISMATCH_KEYS:
        logger.info("mismatch_card_suppressed_duplicate", extra={"list_id": list_id, "task_id": mismatch.task.id})
        record_event("Card suppressed", "Duplicate mismatch already posted", {"list_id": list_id, "task_id": mismatch.task.id})
        return

    explanation = GeminiService().explain_mismatch(mismatch)
    blocks = build_mismatch_blocks(mismatch, explanation)
    logger.info(
        "mismatch_card_ready list_id=%s task_id=%s block_count=%s",
        list_id,
        mismatch.task.id,
        len(blocks),
        extra={"list_id": list_id, "task_id": mismatch.task.id, "block_count": len(blocks)},
    )

    try:
        logger.info("mismatch_card_post_entered list_id=%s task_id=%s channel=%s", list_id, mismatch.task.id, channel, extra={"list_id": list_id, "task_id": mismatch.task.id, "channel": channel})
        client.chat_postMessage(
            channel=channel,
            text=f"Potentially stale task: {mismatch.task.title}",
            blocks=blocks,
        )
    except Exception:
        logger.exception("mismatch_card_post_failed", extra={"list_id": list_id, "task_id": mismatch.task.id})
        record_event("Card failed", "Failed to post mismatch card", {"list_id": list_id, "task_id": mismatch.task.id})
        return

    _POSTED_MISMATCH_KEYS.add(dedupe_key)
    increment_stat("cards_posted")
    record_event("Card posted", f"Task: {mismatch.task.title}", {"list_id": list_id, "task_id": mismatch.task.id})
    logger.info("mismatch_card_posted list_id=%s task_id=%s", list_id, mismatch.task.id, extra={"list_id": list_id, "task_id": mismatch.task.id})


def _extract_list_id(event: dict[str, Any]) -> str | None:
    context = event.get("context") or {}
    entities = context.get("entities") or []

    for entity in entities:
        if isinstance(entity, dict) and entity.get("type") == LIST_ENTITY_TYPE:
            value = entity.get("value")
            return str(value) if value else None

    return None


def _resolve_response_channel(event: dict[str, Any]) -> str | None:
    direct_candidates = (
        event.get("channel"),
        event.get("channel_id"),
        (event.get("container") or {}).get("channel_id"),
        (event.get("context") or {}).get("channel_id"),
    )
    for candidate in direct_candidates:
        if candidate:
            return str(candidate)

    user = event.get("user") or event.get("user_id")
    return str(user) if user else None


def _resolve_user_id(event: dict[str, Any]) -> str | None:
    user = event.get("user") or event.get("user_id")
    return str(user) if user else None


def _dedupe_key(list_id: str, task_id: str, reason: str, status: str) -> str:
    return f"{list_id}:{task_id}:{reason}:{status}"


def _print_app_context_changed_event(event: dict[str, Any]) -> None:
    context = event.get("context") or {}
    entities = context.get("entities") or event.get("entities") or []

    logger.debug(
        "app_context_changed_event_received",
        extra={
            "event_type": event.get("type"),
            "event_context": event.get("event_context"),
            "entity_count": len(entities),
            "entities": [
                {"type": entity.get("type"), "value": entity.get("value")}
                for entity in entities
                if isinstance(entity, dict)
            ],
        },
    )

