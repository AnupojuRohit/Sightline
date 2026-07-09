import logging
import re
from typing import Any, Iterable

from models.mismatch import GitHubReference, GitHubState
from models.task import Task

logger = logging.getLogger(__name__)

GITHUB_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/(?:pull|issues)/(?P<number>\d+)",
    re.IGNORECASE,
)


class GitHubChecker:
    def check_task(self, task: Task) -> list[GitHubState]:
        states = self._states_from_task_metadata(task)
        if states:
            return states

        references = self.find_references(task)
        if references:
            logger.info(
                "github_references_found",
                extra={"task_id": task.id, "reference_count": len(references)},
            )

        return [
            GitHubState(
                reference=reference,
                state="unknown",
                url=reference.url,
                reason="GitHub MCP checker is not configured.",
            )
            for reference in references
        ]

    def find_references(self, task: Task) -> list[GitHubReference]:
        text = " ".join(self._candidate_text(task))
        references: list[GitHubReference] = []

        for match in GITHUB_URL_RE.finditer(text):
            url = match.group(0)
            references.append(
                GitHubReference(
                    kind="pull_request" if "/pull/" in url.lower() else "issue",
                    number=int(match.group("number")),
                    owner=match.group("owner"),
                    repo=match.group("repo"),
                    url=url,
                )
            )

        return references

    def _candidate_text(self, task: Task) -> Iterable[str]:
        yield task.title

        if task.description:
            yield task.description

        if task.url:
            yield task.url

        for value in task.raw_fields.values():
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                yield from (str(v) for v in value.values() if isinstance(v, (str, int)))
            elif isinstance(value, list):
                yield from (str(v) for v in value if isinstance(v, (str, int)))

    def _states_from_task_metadata(self, task: Task) -> list[GitHubState]:
        raw_github = task.raw_fields.get("github")
        if not raw_github:
            return []

        values = raw_github if isinstance(raw_github, list) else [raw_github]
        return [
            state
            for value in values
            if isinstance(value, dict)
            for state in [self._state_from_mapping(value)]
            if state is not None
        ]

    def _state_from_mapping(self, value: dict[str, Any]) -> GitHubState | None:
        number = value.get("number")
        if number is None:
            return None

        try:
            parsed_number = int(number)
        except (TypeError, ValueError):
            return None

        kind = str(value.get("kind") or value.get("type") or "pull_request")
        url = value.get("url")
        return GitHubState(
            reference=GitHubReference(
                kind=kind,
                number=parsed_number,
                owner=value.get("owner"),
                repo=value.get("repo"),
                url=url,
            ),
            state=str(value.get("state") or "unknown").lower(),
            merged=bool(value.get("merged")),
            title=value.get("title"),
            url=url,
        )
