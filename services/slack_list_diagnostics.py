from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse


SLACK_LIST_ID_RE = re.compile(r"\bF[A-Z0-9]{8,}\b")


def extract_slack_list_id(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = value.strip()
    match = SLACK_LIST_ID_RE.search(cleaned)
    return match.group(0) if match else cleaned or None


def diagnose_slack_list_reference(client: Any, reference: str | None) -> dict[str, Any]:
    candidates = _candidate_ids(reference)
    results: list[dict[str, Any]] = []

    for candidate in candidates:
        results.append(_check_list_items(client, candidate))
        results.append(_check_files_info(client, candidate))

    return {
        "input": reference,
        "candidateIds": candidates,
        "checks": results,
        "filesList": _check_files_list(client),
        "notes": [
            "Slack SDK exposes slackLists.items.list for a known List ID.",
            "The installed Slack SDK does not expose a Slack Lists enumerate/list-all method.",
            "files.list/files.info require files:read and may identify F-prefixed objects when that scope is granted.",
        ],
    }


def _candidate_ids(reference: str | None) -> list[str]:
    if not reference:
        return []

    candidates: list[str] = []
    for match in SLACK_LIST_ID_RE.finditer(reference):
        if match.group(0) not in candidates:
            candidates.append(match.group(0))

    fallback = reference.strip()
    if fallback and fallback not in candidates:
        candidates.append(fallback)

    return candidates


def _check_list_items(client: Any, list_id: str) -> dict[str, Any]:
    try:
        response = client.slackLists_items_list(list_id=list_id, limit=1)
        data = _response_data(response)
        return {
            "mechanism": "slackLists.items.list",
            "candidateId": list_id,
            "ok": bool(data.get("ok", True)),
            "error": data.get("error"),
            "itemCount": len(data.get("items") or data.get("list_items") or data.get("rows") or []),
            "acceptedAsListId": bool(data.get("ok", True)),
        }
    except SlackApiError as error:
        data = _response_data(error.response)
        return {
            "mechanism": "slackLists.items.list",
            "candidateId": list_id,
            "ok": False,
            "error": data.get("error"),
            "needed": data.get("needed"),
            "provided": data.get("provided"),
            "acceptedAsListId": False,
        }
    except Exception as error:
        return _diagnostic_exception("slackLists.items.list", str(list_id), error)


def _check_files_info(client: Any, file_id: str) -> dict[str, Any]:
    try:
        response = client.files_info(file=file_id)
        data = _response_data(response)
        file_info = data.get("file") if isinstance(data.get("file"), dict) else {}
        return {
            "mechanism": "files.info",
            "candidateId": file_id,
            "ok": bool(data.get("ok", True)),
            "error": data.get("error"),
            "file": _safe_file_summary(file_info),
        }
    except SlackApiError as error:
        data = _response_data(error.response)
        return {
            "mechanism": "files.info",
            "candidateId": file_id,
            "ok": False,
            "error": data.get("error"),
            "needed": data.get("needed"),
            "provided": data.get("provided"),
        }
    except Exception as error:
        return _diagnostic_exception("files.info", str(file_id), error)


def _check_files_list(client: Any) -> dict[str, Any]:
    try:
        response = client.files_list(count=100)
        data = _response_data(response)
        files = data.get("files") or []
        summaries = [
            _safe_file_summary(file_info)
            for file_info in files
            if isinstance(file_info, dict) and str(file_info.get("id") or "").startswith("F")
        ]
        return {
            "ok": bool(data.get("ok", True)),
            "error": data.get("error"),
            "fileCount": len(files),
            "fPrefixedFiles": summaries[:25],
        }
    except SlackApiError as error:
        data = _response_data(error.response)
        return {
            "ok": False,
            "error": data.get("error"),
            "needed": data.get("needed"),
            "provided": data.get("provided"),
        }
    except Exception as error:
        result = _diagnostic_exception("files.list", None, error)
        result.pop("candidateId", None)
        return result


def _response_data(response: Any) -> dict[str, Any]:
    if isinstance(response, Mapping):
        return dict(response)

    if isinstance(response, SlackResponse):
        data = response.data
        return data if isinstance(data, dict) else {"ok": False, "error": "invalid_slack_response_data"}

    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return data

    return {"ok": False, "error": "unsupported_response_type", "details": type(response).__name__}


def _diagnostic_exception(mechanism: str, candidate_id: str | None, error: Exception) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mechanism": mechanism,
        "ok": False,
        "error": "diagnostic_failed",
        "details": f"{type(error).__name__}: {error}",
    }
    if candidate_id is not None:
        result["candidateId"] = candidate_id
    return result


def _safe_file_summary(file_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": file_info.get("id"),
        "title": file_info.get("title"),
        "mode": file_info.get("mode"),
        "mimetype": file_info.get("mimetype"),
        "filetype": file_info.get("filetype"),
    }
