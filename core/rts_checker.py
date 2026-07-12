import logging
import json
import re
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from models.mismatch import RTSEvidence
from models.task import Task
from services.runtime_status import record_event
from services.slack_oauth import SlackOAuthRequiredError, require_user_token

logger = logging.getLogger(__name__)

DONE_TERMS = ("done", "completed", "complete", "merged", "shipped", "fixed", "resolved")
MAX_SEARCH_RESULTS = 3


class RTSChecker:
    def __init__(self, client: Any | None = None):
        self.client = client

    def check_task(self, task: Task, user_id: str | None = None) -> list[RTSEvidence]:
        logger.info("rts_check_entered task_id=%s client_present=%s", task.id, self.client is not None, extra={"task_id": task.id, "client_present": self.client is not None})
        if self.client is None:
            evidence = self._evidence_from_task_metadata(task)
            logger.info("rts_metadata_only task_id=%s evidence_count=%s", task.id, len(evidence), extra={"task_id": task.id, "evidence_count": len(evidence)})
            return evidence

        evidence: list[RTSEvidence] = self._evidence_from_task_metadata(task)
        resolved_user_id = user_id or self._user_id_from_task(task)
        try:
            user_token = require_user_token(resolved_user_id)
        except SlackOAuthRequiredError as error:
            logger.warning(
                "rts_search_skipped_missing_user_token task_id=%s user_id_present=%s",
                task.id,
                bool(resolved_user_id),
                extra={"task_id": task.id, "user_id": resolved_user_id},
            )
            record_event("RTS skipped", str(error), {"task_id": task.id, "user_id": resolved_user_id})
            return evidence

        queries = self.build_queries(task)
        logger.info(
            "rts_search_ready task_id=%s query_count=%s user_id_present=%s",
            task.id,
            len(queries),
            bool(resolved_user_id),
            extra={"task_id": task.id, "query_count": len(queries), "user_id_present": bool(resolved_user_id)},
        )
        for query in queries:
            try:
                logger.info("rts_search_api_call task_id=%s query=%s", task.id, query, extra={"task_id": task.id, "query": query})
                response = self._search_messages(user_token, query)
            except Exception:
                logger.exception("rts_search_unexpected_error", extra={"task_id": task.id, "query": query})
                continue

            if not response.get("ok", True):
                error = response.get("error")
                if error in {"not_allowed_token_type", "missing_scope", "invalid_auth"}:
                    logger.warning(
                        "rts_search_skipped_token_not_allowed",
                        extra={"task_id": task.id, "query": query, "error": error},
                    )
                    record_event("RTS skipped", f"Slack search auth failed: {error}", {"task_id": task.id})
                    continue

                logger.warning(
                    "rts_search_failed",
                    extra={"task_id": task.id, "query": query, "error": error},
                )
                record_event("RTS failed", f"Slack search failed: {error}", {"task_id": task.id, "query": query})
                continue

            query_evidence = self._evidence_from_response(query, response)
            logger.info(
                "rts_search_success task_id=%s query=%s result_count=%s",
                task.id,
                query,
                len(query_evidence),
                extra={"task_id": task.id, "query": query, "result_count": len(query_evidence)},
            )
            evidence.extend(query_evidence)

        logger.info("rts_check_complete task_id=%s evidence_count=%s", task.id, len(evidence), extra={"task_id": task.id, "evidence_count": len(evidence)})
        return evidence

    def build_queries(self, task: Task) -> list[str]:
        candidates = list(self._reference_terms(task))
        if task.title:
            candidates.append(f'"{task.title}"')

        deduped: list[str] = []
        for candidate in candidates:
            cleaned = candidate.strip()
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)

        return deduped[:3]

    def _reference_terms(self, task: Task) -> Iterable[str]:
        text = " ".join(
            value
            for value in (task.title, task.description, task.url)
            if value
        )

        for match in re.finditer(r"https?://github\.com/\S+", text, re.IGNORECASE):
            yield match.group(0)

        for match in re.finditer(r"#(\d+)", text):
            yield match.group(0)

    def _evidence_from_task_metadata(self, task: Task) -> list[RTSEvidence]:
        raw_rts = task.raw_fields.get("rts")
        if not raw_rts:
            return []

        values = raw_rts if isinstance(raw_rts, list) else [raw_rts]
        evidence: list[RTSEvidence] = []
        for value in values:
            if isinstance(value, dict):
                text = str(value.get("text") or "")
                evidence.append(
                    RTSEvidence(
                        query=str(value.get("query") or task.title),
                        text=text,
                        url=value.get("url"),
                        user=value.get("user"),
                        timestamp=value.get("timestamp"),
                        confirms_done=bool(value.get("confirms_done")) or self._confirms_done(text),
                    )
                )
        return evidence

    def _user_id_from_task(self, task: Task) -> str | None:
        user_id = task.raw_fields.get("slack_user_id")
        return str(user_id) if user_id else None

    def _search_messages(self, user_token: str, query: str) -> dict[str, Any]:
        params = urlencode(
            {
                "query": query,
                "count": MAX_SEARCH_RESULTS,
                "sort": "timestamp",
                "sort_dir": "desc",
            }
        )
        request = Request(
            f"https://slack.com/api/search.messages?{params}",
            headers={"Authorization": f"Bearer {user_token}"},
            method="GET",
        )

        try:
            with urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            body = error.read().decode("utf-8")
            decoded = self._decode_response(body)
            decoded.setdefault("ok", False)
            decoded.setdefault("error", f"http_{error.code}")
            return decoded
        except URLError as error:
            return {"ok": False, "error": f"network_error:{error.reason}"}

        return self._decode_response(body)

    def _decode_response(self, body: str) -> dict[str, Any]:
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"ok": False, "error": "invalid_json_response"}

    def _evidence_from_response(self, query: str, response: Any) -> list[RTSEvidence]:
        matches = response.get("messages", {}).get("matches", []) if isinstance(response, dict) else []
        evidence: list[RTSEvidence] = []

        for match in matches[:MAX_SEARCH_RESULTS]:
            text = str(match.get("text") or "")
            evidence.append(
                RTSEvidence(
                    query=query,
                    text=text,
                    url=match.get("permalink"),
                    user=match.get("user"),
                    timestamp=match.get("ts"),
                    confirms_done=self._confirms_done(text),
                )
            )

        return evidence

    def _confirms_done(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in DONE_TERMS)
