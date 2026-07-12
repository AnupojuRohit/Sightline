import logging
import os
from dataclasses import replace
from datetime import datetime
from typing import Any, Optional

from slack_sdk.errors import SlackApiError

from models.task import Task
from services.mock_loader import load_mock_tasks

logger = logging.getLogger(__name__)

LIST_ITEMS_METHOD = "slackLists.items.list"
LIST_UPDATE_METHOD = "slackLists.items.update"
USE_MOCK_LISTS_ENV = "SIGHTLINE_USE_MOCK_LISTS"
ENABLE_LIST_UPDATES_ENV = "SIGHTLINE_ENABLE_LIST_UPDATES"


class SlackListLoader:
    def __init__(self, client: Any):
        self.client = client

    def load_tasks(self, list_id: str) -> list[Task]:
        logger.info("slack_list_load_entered list_id=%s", list_id, extra={"list_id": list_id})
        if self._truthy(os.getenv(USE_MOCK_LISTS_ENV)):
            logger.info("slack_list_load_mock_mode list_id=%s", list_id, extra={"list_id": list_id})
            return [
                replace(task, list_id=list_id, item_id=task.item_id or task.id)
                for task in load_mock_tasks()
            ]

        response = self._list_items(list_id)
        if not response:
            return []

        items = self._extract_items(response)
        tasks = [
            task
            for item in items
            for task in [self._task_from_item(list_id, item)]
            if task is not None
        ]

        logger.info("slack_list_loaded list_id=%s task_count=%s", list_id, len(tasks), extra={"list_id": list_id, "task_count": len(tasks)})
        return tasks

    def update_task_status(self, list_id: str, item_id: str | None, status: str) -> bool:
        logger.info(
            "slack_list_update_entered list_id=%s item_id=%s status=%s",
            list_id,
            item_id,
            status,
            extra={"list_id": list_id, "item_id": item_id, "status": status},
        )
        if not item_id:
            logger.warning("slack_list_update_missing_item_id", extra={"list_id": list_id})
            return False

        if self._truthy(os.getenv(USE_MOCK_LISTS_ENV)):
            logger.info(
                "slack_list_mock_update",
                extra={"list_id": list_id, "item_id": item_id, "status": status},
            )
            return True

        if not self._truthy(os.getenv(ENABLE_LIST_UPDATES_ENV)):
            logger.info(
                "slack_list_update_skipped",
                extra={"list_id": list_id, "item_id": item_id, "reason": "updates_disabled"},
            )
            return False

        try:
            logger.info("slack_list_update_api_call list_id=%s item_id=%s", list_id, item_id, extra={"list_id": list_id, "item_id": item_id})
            response = self.client.api_call(
                api_method=LIST_UPDATE_METHOD,
                json={
                    "list_id": list_id,
                    "item_id": item_id,
                    "fields": {"status": status},
                },
            )
        except SlackApiError as error:
            logger.warning(
                "slack_list_update_failed",
                extra={
                    "list_id": list_id,
                    "item_id": item_id,
                    "error": error.response.get("error"),
                },
            )
            return False
        except Exception:
            logger.exception("slack_list_update_unexpected_error", extra={"list_id": list_id, "item_id": item_id})
            return False

        if isinstance(response, dict) and not response.get("ok", False):
            logger.warning(
                "slack_list_update_not_ok",
                extra={"list_id": list_id, "item_id": item_id, "error": response.get("error")},
            )
            return False

        logger.info("slack_list_update_success list_id=%s item_id=%s status=%s", list_id, item_id, status, extra={"list_id": list_id, "item_id": item_id, "status": status})
        return bool(response.get("ok", False)) if isinstance(response, dict) else False

    def _list_items(self, list_id: str) -> dict[str, Any] | None:
        try:
            logger.info("slack_list_api_call method=%s list_id=%s", LIST_ITEMS_METHOD, list_id, extra={"list_id": list_id, "method": LIST_ITEMS_METHOD})
            response = self.client.api_call(
                api_method=LIST_ITEMS_METHOD,
                json={"list_id": list_id},
            )
        except SlackApiError as error:
            logger.warning(
                "slack_list_load_failed list_id=%s error=%s",
                list_id,
                error.response.get("error"),
                extra={"list_id": list_id, "error": error.response.get("error")},
            )
            return None
        except Exception:
            logger.exception("slack_list_load_unexpected_error", extra={"list_id": list_id})
            return None

        if isinstance(response, dict) and not response.get("ok", True):
            logger.warning(
                "slack_list_load_not_ok",
                extra={"list_id": list_id, "error": response.get("error")},
            )
            return None

        item_count = len(self._extract_items(response)) if isinstance(response, dict) else 0
        logger.info("slack_list_api_success list_id=%s item_count=%s", list_id, item_count, extra={"list_id": list_id, "item_count": item_count})
        return response if isinstance(response, dict) else None

    def _extract_items(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        items = response.get("items") or response.get("list_items") or response.get("rows") or []
        return [item for item in items if isinstance(item, dict)]

    def _task_from_item(self, list_id: str, item: dict[str, Any]) -> Optional[Task]:
        fields = self._normalise_fields(item)
        title = self._first_value(item, fields, ("title", "name", "task", "summary"))
        if not title:
            return None

        item_id = self._first_value(item, fields, ("item_id", "id", "row_id"))
        return Task(
            id=str(item_id or title),
            title=str(title),
            owner=self._optional_str(self._first_value(item, fields, ("owner", "assignee", "assigned_to"))),
            status=str(self._first_value(item, fields, ("status", "state")) or "Unknown"),
            priority=str(self._first_value(item, fields, ("priority",)) or "Normal"),
            due_date=self._parse_datetime(self._first_value(item, fields, ("due_date", "due", "deadline"))),
            blocked_by=[],
            description=self._optional_str(self._first_value(item, fields, ("description", "notes"))),
            list_id=list_id,
            item_id=self._optional_str(item_id),
            url=self._optional_str(self._first_value(item, fields, ("url", "link"))),
            raw_fields={**fields, "slack_item": item},
        )

    def _normalise_fields(self, item: dict[str, Any]) -> dict[str, Any]:
        raw_fields = item.get("fields") or {}
        if isinstance(raw_fields, dict):
            return dict(raw_fields)

        fields: dict[str, Any] = {}
        if isinstance(raw_fields, list):
            for field in raw_fields:
                if not isinstance(field, dict):
                    continue
                key = field.get("key") or field.get("name") or field.get("id") or field.get("label")
                value = field.get("value") if "value" in field else field.get("text")
                if key:
                    fields[str(key)] = self._display_value(value)

        return fields

    def _first_value(
        self,
        item: dict[str, Any],
        fields: dict[str, Any],
        names: tuple[str, ...],
    ) -> Any | None:
        lowered_fields = {str(key).lower(): value for key, value in fields.items()}
        lowered_item = {str(key).lower(): value for key, value in item.items()}

        for name in names:
            lowered_name = name.lower()
            if lowered_name in lowered_fields:
                return self._display_value(lowered_fields[lowered_name])
            if lowered_name in lowered_item:
                return self._display_value(lowered_item[lowered_name])

        return None

    def _display_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            for key in ("text", "value", "name", "title", "label"):
                if key in value and value[key] is not None:
                    return value[key]

            if "selected_option" in value:
                return self._display_value(value["selected_option"])

            if "users" in value and isinstance(value["users"], list):
                return ", ".join(str(user) for user in value["users"])

        if isinstance(value, list):
            displayed = [self._display_value(item) for item in value]
            return ", ".join(str(item) for item in displayed if item is not None)

        return value

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None

        return None

    def _optional_str(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def _truthy(self, value: str | None) -> bool:
        return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}
