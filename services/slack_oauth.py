from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

_USER_TOKENS: dict[str, str] = {}
_LOCK = threading.RLock()
_TOKEN_STORE_PATH = Path(os.getenv("SIGHTLINE_TOKEN_STORE_PATH", ".token_store.json")).resolve()
logger = logging.getLogger(__name__)


class SlackOAuthError(RuntimeError):
    pass


class SlackOAuthRequiredError(RuntimeError):
    pass


def oauth_missing_env_vars() -> list[str]:
    required = ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_OAUTH_REDIRECT_URI")
    return [name for name in required if not os.getenv(name)]


def oauth_is_configured() -> bool:
    return not oauth_missing_env_vars()


def log_oauth_startup_status() -> None:
    missing = oauth_missing_env_vars()
    if missing:
        logger.warning(
            "RTS live search disabled - OAuth env not configured",
            extra={"missing_env_vars": missing},
        )


def load_token_store() -> None:
    with _LOCK:
        if not _TOKEN_STORE_PATH.exists():
            return

        try:
            raw = json.loads(_TOKEN_STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("slack_oauth_token_store_load_failed", extra={"path": str(_TOKEN_STORE_PATH)})
            return

        if not isinstance(raw, dict):
            logger.warning("slack_oauth_token_store_invalid", extra={"path": str(_TOKEN_STORE_PATH)})
            return

        token_map = raw.get("tokens") if isinstance(raw.get("tokens"), dict) else raw

        for key, value in token_map.items():
            if isinstance(key, str) and isinstance(value, str):
                _USER_TOKENS[key] = value


def build_authorize_url() -> str:
    client_id = _require_env("SLACK_CLIENT_ID")
    redirect_uri = _require_env("SLACK_OAUTH_REDIRECT_URI")

    query = urlencode(
        {
            "client_id": client_id,
            "user_scope": "search:read",
            "redirect_uri": redirect_uri,
        }
    )
    return f"https://slack.com/oauth/v2/authorize?{query}"


def exchange_code_for_token(code: str) -> dict[str, Any]:
    client_id = _require_env("SLACK_CLIENT_ID")
    client_secret = _require_env("SLACK_CLIENT_SECRET")
    redirect_uri = _require_env("SLACK_OAUTH_REDIRECT_URI")

    payload = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")

    request = Request(
        "https://slack.com/api/oauth.v2.access",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except HTTPError as error:
        body = error.read().decode("utf-8")
        return _decode_response(body, fallback={"ok": False, "error": f"http_{error.code}"})
    except URLError as error:
        raise SlackOAuthError(f"Slack OAuth request failed: {error.reason}") from error

    return _decode_response(body)


def store_user_token(user_id: str, access_token: str, team_id: str | None = None) -> None:
    with _LOCK:
        token = str(access_token)
        uid = str(user_id)
        _USER_TOKENS[uid] = token
        if team_id:
            _USER_TOKENS[_scoped_key(uid, str(team_id))] = token
        _save_token_store_unlocked()


def get_user_token(user_id: str | None = None, team_id: str | None = None) -> str | None:
    with _LOCK:
        if user_id and team_id:
            scoped = _USER_TOKENS.get(_scoped_key(str(user_id), str(team_id)))
            if scoped:
                return scoped

        if user_id:
            direct = _USER_TOKENS.get(str(user_id))
            if direct:
                return direct

            matches = [
                value
                for key, value in _USER_TOKENS.items()
                if key.endswith(f":{user_id}")
            ]
            if len(matches) == 1:
                return matches[0]

        unique_tokens = set(_USER_TOKENS.values())
        if len(unique_tokens) == 1:
            return next(iter(unique_tokens))

        return None


def has_any_user_token() -> bool:
    with _LOCK:
        return bool(_USER_TOKENS)


def require_user_token(user_id: str | None = None, team_id: str | None = None) -> str:
    token = get_user_token(user_id=user_id, team_id=team_id)
    if token:
        return token

    if user_id:
        raise SlackOAuthRequiredError(
            f"No Slack user token is on file for user {user_id}. Complete /slack/oauth/authorize first."
        )

    raise SlackOAuthRequiredError(
        "No Slack user token is on file. Complete /slack/oauth/authorize first."
    )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SlackOAuthError(f"Missing required environment variable: {name}")
    return value


def _decode_response(body: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return fallback or {"ok": False, "error": "invalid_json_response"}

    return parsed if isinstance(parsed, dict) else (fallback or {"ok": False, "error": "invalid_response"})


def _save_token_store_unlocked() -> None:
    try:
        _TOKEN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_STORE_PATH.write_text(
            json.dumps({"tokens": _USER_TOKENS}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.exception("slack_oauth_token_store_save_failed", extra={"path": str(_TOKEN_STORE_PATH)})
        raise SlackOAuthError(f"Could not persist Slack OAuth token store at {_TOKEN_STORE_PATH}") from exc


def _scoped_key(user_id: str, team_id: str) -> str:
    return f"{team_id}:{user_id}"


load_token_store()
