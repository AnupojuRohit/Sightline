from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()

from services.demo_console import build_demo_console_payload
from services.demo_console import build_scan_console_payload
from services.runtime_status import snapshot
from services.scan_pipeline import run_slack_list_scan
from services.slack_list_diagnostics import diagnose_slack_list_reference
from services.slack_list_diagnostics import extract_slack_list_id
from services.slack_oauth import (
    SlackOAuthError,
    build_authorize_url,
    exchange_code_for_token,
    has_any_user_token,
    oauth_is_configured,
    oauth_missing_env_vars,
    store_user_token,
)

HOST = "127.0.0.1"
PORT = 5001
ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "templates" / "dashboard.html"


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path in {"/", "/index.html"}:
            self._send_html(TEMPLATE.read_text(encoding="utf-8"))
            return

        if path in {"/authorize", "/slack/oauth/authorize"}:
            if not oauth_is_configured():
                self._send_json(
                    {
                        "ok": False,
                        "error": "oauth_not_configured",
                        "missing_env_vars": oauth_missing_env_vars(),
                    },
                    status=503,
                )
                return
            try:
                self._send_redirect(build_authorize_url())
            except SlackOAuthError as error:
                self._send_json({"ok": False, "error": str(error)}, status=503)
            return

        if path in {"/oauth/callback", "/slack/oauth/callback"}:
            self._handle_oauth_callback()
            return

        if path == "/api/demo":
            self._send_json(build_demo_console_payload())
            return

        if path == "/api/scan":
            self._handle_scan()
            return

        if path == "/api/list-diagnostics":
            self._handle_list_diagnostics()
            return

        if path == "/api/health":
            self._send_json(self._health_payload())
            return

        if path == "/api/events":
            self._send_json(snapshot())
            return

        self.send_error(404, "Not found")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _handle_oauth_callback(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        error = self._first_query_value(query, "error")
        if error:
            self._send_json({"ok": False, "error": error}, status=400)
            return

        code = self._first_query_value(query, "code")
        if not code:
            self._send_json({"ok": False, "error": "missing_code"}, status=400)
            return

        try:
            response = exchange_code_for_token(code)
        except SlackOAuthError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=500)
            return

        if not response.get("ok", False):
            self._send_json(response, status=400)
            return

        authed_user = response.get("authed_user") or {}
        team = response.get("team") or {}
        team_id = team.get("id")
        user_id = authed_user.get("id")
        access_token = authed_user.get("access_token")

        if not user_id or not access_token:
            self._send_json({"ok": False, "error": "missing_authed_user_access_token"}, status=400)
            return

        store_user_token(str(user_id), str(access_token), team_id=str(team_id) if team_id else None)
        self._send_redirect("/?oauth=success")

    def _first_query_value(self, query: dict[str, list[str]], key: str) -> str | None:
        values = query.get(key) or []
        return values[0] if values else None

    def _handle_scan(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        list_reference = (
            self._first_query_value(query, "list_id")
            or os.getenv("SIGHTLINE_DEFAULT_LIST_ID")
            or os.getenv("SIGHTLINE_LIST_ID")
        )
        list_id = extract_slack_list_id(list_reference)
        user_id = self._first_query_value(query, "user_id")

        if not list_id:
            self._send_json(
                {
                    "ok": False,
                    "error": "missing_list_id",
                    "message": "Set SIGHTLINE_DEFAULT_LIST_ID or pass ?list_id=<Slack List ID>.",
                },
                status=400,
            )
            return

        if _truthy(os.getenv("SIGHTLINE_USE_MOCK_LISTS")):
            self._send_json(
                {
                    "ok": False,
                    "error": "mock_lists_enabled",
                    "message": "Set SIGHTLINE_USE_MOCK_LISTS=false before running a real dashboard scan.",
                },
                status=409,
            )
            return

        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            self._send_json(
                {"ok": False, "error": "missing_slack_bot_token"},
                status=503,
            )
            return

        try:
            result = run_slack_list_scan(WebClient(token=bot_token), str(list_id), user_id=user_id)
        except Exception as error:
            self._send_json(
                {
                    "ok": False,
                    "error": "scan_failed",
                    "message": str(error),
                },
                status=500,
            )
            return

        self._send_json({"ok": True, **build_scan_console_payload(result)})

    def _handle_list_diagnostics(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        reference = (
            self._first_query_value(query, "list_id")
            or self._first_query_value(query, "url")
            or os.getenv("SIGHTLINE_DEFAULT_LIST_ID")
            or os.getenv("SIGHTLINE_LIST_ID")
        )

        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            self._send_json({"ok": False, "error": "missing_slack_bot_token"}, status=503)
            return

        self._send_json(
            {
                "ok": True,
                **diagnose_slack_list_reference(WebClient(token=bot_token), reference),
            }
        )

    def _health_payload(self) -> dict[str, object]:
        return {
            "slack": {
                "botTokenPresent": bool(os.getenv("SLACK_BOT_TOKEN")),
                "appTokenPresent": bool(os.getenv("SLACK_APP_TOKEN")),
            },
            "github": {
                "tokenPresent": bool(os.getenv("GITHUB_TOKEN")),
            },
            "lists": {
                "defaultListIdPresent": bool(os.getenv("SIGHTLINE_DEFAULT_LIST_ID") or os.getenv("SIGHTLINE_LIST_ID")),
                "mockListsEnabled": _truthy(os.getenv("SIGHTLINE_USE_MOCK_LISTS")),
                "updatesEnabled": _truthy(os.getenv("SIGHTLINE_ENABLE_LIST_UPDATES")),
            },
            "rts": {
                "oauthConfigured": oauth_is_configured(),
                "missingOAuthEnvVars": oauth_missing_env_vars(),
                "userTokenPresent": has_any_user_token(),
            },
            "session": snapshot(max_events=0),
        }


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Sightline demo console running at http://{HOST}:{PORT}")
    server.serve_forever()


def create_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer((HOST, PORT), DashboardHandler)


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    run()
