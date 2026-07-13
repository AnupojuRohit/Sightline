from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse


SLACK_LIST_ID_RE = re.compile(r"\bF[A-Z0-9]{8,}\b")

# Sentinel used to distinguish "attribute missing" from "attribute is None".
_SENTINEL = object()


def extract_slack_list_id(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = value.strip()
    match = SLACK_LIST_ID_RE.search(cleaned)
    return match.group(0) if match else cleaned or None


def diagnose_slack_list_reference(client: Any, reference: str | None) -> dict[str, Any]:
    try:
        candidates = _candidate_ids(reference)
        results: list[dict[str, Any]] = []

        for candidate in candidates:
            results.append(_check_list_items(client, candidate))
            results.append(_check_files_info(client, candidate))

        return {
            "ok": True,
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
    except Exception as exc:
        return {
            "ok": False,
            "error": "diagnostics_failed",
            "details": f"{type(exc).__name__}: {exc}",
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
    """Extract the JSON payload from *any* Slack SDK response type.

    This function **never** calls ``dict(response)`` on a ``SlackResponse``
    because ``SlackResponse.__iter__`` is a *pagination* iterator, not a
    key iterator — ``dict()`` therefore raises ``ValueError`` / ``TypeError``.

    Handling order (intentional):
    1. ``None`` — early-out so later attribute access is safe.
    2. Plain ``dict`` — the most common case, returned as-is.
    3. ``.data`` attribute (``SlackResponse`` and look-alikes) — the official
       SDK way to access the JSON body.  Checked *before* the ``Mapping``
       ABC because ``SlackResponse`` registers as a ``Mapping``.
    4. ``Mapping`` that is **not** a ``SlackResponse`` — safe to convert
       with ``dict()``.
    5. Fallback — return a descriptive error dict.

    The entire body is wrapped in a blanket ``except Exception`` so that
    this helper can **never** propagate an exception to the caller.
    """
    try:
        # --- 1. None / missing ------------------------------------------------
        if response is None:
            return {"ok": False, "error": "no_response", "details": "response was None"}

        # --- 2. Plain dict (most common for mocks / already-decoded) ----------
        if isinstance(response, dict):
            return response

        # --- 3. SlackResponse or anything with a .data dict -------------------
        #     Check the concrete type first, then fall back to duck-typing so
        #     we also handle subclasses and third-party wrappers.
        if isinstance(response, SlackResponse):
            body = response.data
            if isinstance(body, dict):
                return body
            return {"ok": False, "error": "invalid_slack_response_data",
                    "details": f"SlackResponse.data was {type(body).__name__}, expected dict"}

        data_attr = getattr(response, "data", _SENTINEL)
        if data_attr is not _SENTINEL and isinstance(data_attr, dict):
            return data_attr

        # --- 4. Other Mapping (NOT SlackResponse) — safe to dict() ------------
        if isinstance(response, Mapping):
            try:
                return dict(response)
            except (ValueError, TypeError) as exc:
                return {"ok": False, "error": "mapping_conversion_failed", "details": str(exc)}

        # --- 5. Fallback ------------------------------------------------------
        return {"ok": False, "error": "unsupported_response_type",
                "details": type(response).__name__}

    except Exception as exc:
        # Blanket safety net — this function must *never* raise.
        return {"ok": False, "error": "response_extraction_failed",
                "details": f"{type(exc).__name__}: {exc}"}


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
