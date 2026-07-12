import logging
import json
import os
import re
import time
from datetime import datetime
from typing import Any, Iterable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from models.mismatch import GitHubReference, GitHubState
from models.task import Task

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_CACHE_TTL_SECONDS = 180

GITHUB_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/(?:pull|issues)/(?P<number>\d+)",
    re.IGNORECASE,
)


class GitHubStateProvider(Protocol):
    def check_reference(self, reference: GitHubReference) -> GitHubState | dict[str, Any] | None:
        ...


class GitHubChecker:
    def __init__(self, state_provider: GitHubStateProvider | None = None):
        self.state_provider = state_provider or _provider_from_env()

    def check_task(self, task: Task) -> list[GitHubState]:
        logger.info("github_check_entered task_id=%s", task.id, extra={"task_id": task.id})
        references = self.find_references(task)
        if references:
            logger.info(
                "github_references_found task_id=%s reference_count=%s",
                task.id,
                len(references),
                extra={"task_id": task.id, "reference_count": len(references)},
            )
        else:
            logger.info("github_no_references task_id=%s", task.id, extra={"task_id": task.id})

        live_states: list[GitHubState] = []
        if self.state_provider is not None and references:
            live_states = [self._check_reference(reference, task) for reference in references]
            if any(state.state != "unknown" for state in live_states):
                logger.info(
                    "github_check_success_live task_id=%s state_count=%s",
                    task.id,
                    len(live_states),
                    extra={"task_id": task.id, "state_count": len(live_states)},
                )
                return live_states

        metadata_states = self._states_from_task_metadata(task)
        if metadata_states:
            if live_states:
                logger.warning(
                    "github_live_lookup_fell_back_to_metadata",
                    extra={"task_id": task.id, "reference_count": len(references)},
                )
            logger.info(
                "github_check_success_metadata task_id=%s state_count=%s",
                task.id,
                len(metadata_states),
                extra={"task_id": task.id, "state_count": len(metadata_states)},
            )
            return metadata_states

        if live_states:
            logger.info(
                "github_check_unknown_live task_id=%s state_count=%s",
                task.id,
                len(live_states),
                extra={"task_id": task.id, "state_count": len(live_states)},
            )
            return live_states

        logger.info("github_check_no_states task_id=%s", task.id, extra={"task_id": task.id})
        return [self._unknown_state(reference) for reference in references]

    def _check_reference(self, reference: GitHubReference, task: Task) -> GitHubState:
        if self.state_provider is None:
            return self._unknown_state(reference)

        try:
            state = self.state_provider.check_reference(reference)
        except Exception:
            logger.exception(
                "github_reference_check_failed",
                extra={"task_id": task.id, "reference": reference.number},
            )
            return self._unknown_state(reference)

        if isinstance(state, GitHubState):
            return state
        if isinstance(state, dict):
            return self._state_from_mapping({**state, "number": state.get("number", reference.number)}) or self._unknown_state(reference)

        return self._unknown_state(reference)

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
            updated_at=self._parse_datetime(value.get("updated_at")),
            url=url,
        )

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _unknown_state(self, reference: GitHubReference) -> GitHubState:
        return GitHubState(
            reference=reference,
            state="unknown",
            url=reference.url,
            reason="GitHub checker is not configured.",
        )


class LiveGitHubStateProvider:
    def __init__(self, token: str, cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        self.token = token
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, GitHubState]] = {}

    def check_reference(self, reference: GitHubReference) -> GitHubState | dict[str, Any] | None:
        owner = reference.owner
        repo = reference.repo
        number = reference.number

        if not owner or not repo:
            return GitHubState(
                reference=reference,
                state="unknown",
                url=reference.url,
                reason="GitHub reference missing owner or repo.",
            )

        cache_key = f"{owner}/{repo}/{reference.kind}/{number}"
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and cached[0] > now:
            return cached[1]

        try:
            if reference.kind == "issue":
                state = self._fetch_issue_state(reference, owner, repo, number)
            else:
                state = self._fetch_pull_state(reference, owner, repo, number)
        except HTTPError as error:
            if _is_rate_limited(error) and cached:
                logger.warning(
                    "github_rate_limited_using_cached_state",
                    extra={"owner": owner, "repo": repo, "number": number},
                )
                return cached[1]
            logger.warning(
                "github_live_lookup_failed",
                extra={
                    "owner": owner,
                    "repo": repo,
                    "number": number,
                    "status": error.code,
                    "error": _github_error_body(error),
                },
            )
            return GitHubState(
                reference=reference,
                state="unknown",
                url=reference.url,
                reason=f"GitHub API lookup failed with HTTP {error.code}.",
            )
        except URLError as error:
            logger.warning(
                "github_live_lookup_network_failed",
                extra={"owner": owner, "repo": repo, "number": number, "error": str(error.reason)},
            )
            return GitHubState(
                reference=reference,
                state="unknown",
                url=reference.url,
                reason="GitHub API lookup failed due to a network error.",
            )

        self._cache[cache_key] = (now + self.cache_ttl_seconds, state)
        logger.info(
            "github_live_lookup_success repo=%s/%s number=%s kind=%s state=%s",
            owner,
            repo,
            number,
            reference.kind,
            state.state,
            extra={"owner": owner, "repo": repo, "number": number, "kind": reference.kind, "state": state.state},
        )
        return state

    def _fetch_issue_state(self, reference: GitHubReference, owner: str, repo: str, number: int) -> GitHubState:
        path = f"/repos/{owner}/{repo}/issues/{number}"
        payload = self._api_get(path)
        return GitHubState(
            reference=reference,
            state=str(payload.get("state") or "unknown").lower(),
            merged=False,
            title=payload.get("title"),
            updated_at=_parse_github_datetime(payload.get("updated_at")),
            url=payload.get("html_url") or reference.url,
            reason=None,
        )

    def _fetch_pull_state(self, reference: GitHubReference, owner: str, repo: str, number: int) -> GitHubState:
        path = f"/repos/{owner}/{repo}/pulls/{number}"
        payload = self._api_get(path)
        return GitHubState(
            reference=reference,
            state=str(payload.get("state") or "unknown").lower(),
            merged=bool(payload.get("merged")),
            title=payload.get("title"),
            updated_at=_parse_github_datetime(payload.get("updated_at")),
            url=payload.get("html_url") or reference.url,
            reason=None,
        )

    def _api_get(self, path: str) -> dict[str, Any]:
        request = Request(
            f"{GITHUB_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "Sightline-Demo",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )

        with urlopen(request, timeout=10) as response:
            rate_remaining = response.headers.get("X-RateLimit-Remaining")
            if rate_remaining == "0":
                logger.warning("github_rate_limit_near_exhausted")
            body = response.read().decode("utf-8")

        payload = json.loads(body)
        return payload if isinstance(payload, dict) else {}


def _provider_from_env() -> GitHubStateProvider | None:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return None

    ttl_raw = os.getenv("GITHUB_CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS))
    try:
        ttl = max(30, int(ttl_raw))
    except ValueError:
        ttl = DEFAULT_CACHE_TTL_SECONDS

    return LiveGitHubStateProvider(token=token, cache_ttl_seconds=ttl)


def _parse_github_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_rate_limited(error: HTTPError) -> bool:
    return error.code in {403, 429} and error.headers.get("X-RateLimit-Remaining") == "0"


def _github_error_body(error: HTTPError) -> str:
    try:
        body = error.read().decode("utf-8")
    except Exception:
        return ""
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body[:200]
    if isinstance(parsed, dict):
        return str(parsed.get("message") or parsed.get("error") or "")[:200]
    return body[:200]
