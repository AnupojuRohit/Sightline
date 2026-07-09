import logging
import re
from typing import Any, Iterable

from slack_sdk.errors import SlackApiError

from models.mismatch import RTSEvidence
from models.task import Task

logger = logging.getLogger(__name__)

DONE_TERMS = ("done", "completed", "complete", "merged", "shipped", "fixed", "resolved")
MAX_SEARCH_RESULTS = 3


class RTSChecker:
    def __init__(self, client: Any | None = None):
        self.client = client

    def check_task(self, task: Task) -> list[RTSEvidence]:
        if self.client is None:
            return self._evidence_from_task_metadata(task)

        evidence: list[RTSEvidence] = self._evidence_from_task_metadata(task)

        for query in self.build_queries(task):
            try:
                response = self.client.search_messages(
                    query=query,
                    count=MAX_SEARCH_RESULTS,
                    sort="timestamp",
                    sort_dir="desc",
                )
            except SlackApiError as error:
                logger.warning(
                    "rts_search_failed",
                    extra={"task_id": task.id, "query": query, "error": error.response.get("error")},
                )
                continue
            except Exception:
                logger.exception("rts_search_unexpected_error", extra={"task_id": task.id, "query": query})
                continue

            evidence.extend(self._evidence_from_response(query, response))

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
