Sightline
=========

Sightline is a Slack-native Engineering Manager for Slack Lists. It watches the current Slack List context and stays silent unless deterministic evidence shows a task is stale.

Core flow:

```text
Slack List opened
-> app_context_changed
-> Slack List Loader
-> GitHub Checker
-> Slack RTS Checker
-> Mismatch Engine
-> one compact Block Kit card
-> Update Task or Dismiss
```

Sightline is not a chatbot, dashboard, or generic project summary tool. Rules decide whether a task is stale. Gemini only explains a deterministic finding after evidence exists.

Demo Console
------------

Sightline also includes a local judge-facing demo console. It reports live integration readiness, the runtime event feed, and a visual scan payload for the demo video.

```powershell
python dashboard_app.py
```

Open:

```text
http://127.0.0.1:5001
```

Use the console to show:

- Project health and risk signals.
- Current Slack List status vs Sightline's recommended status.
- GitHub and Slack evidence behind each stale-task finding.
- A Slack alert preview that matches the product workflow.
- Live integration status: Slack tokens, GitHub token, RTS OAuth config, and user-token presence.
- Runtime pipeline events: context changed, list loaded, GitHub checked, RTS checked, engine ran, card posted.

Setup
-----

1. Create a Slack app with Socket Mode enabled.
2. Add the bot token, app-level token, and OAuth client settings to `.env`.
3. Install dependencies.
4. Start the app.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Environment
-----------

Required:

```text
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_OAUTH_REDIRECT_URI=
```

Optional:

```text
SIGHTLINE_TOKEN_STORE_PATH=.token_store.json
GITHUB_TOKEN=
GITHUB_CACHE_TTL_SECONDS=180
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
LOG_LEVEL=INFO
SLACK_AUTH_TEST_ON_STARTUP=false
SIGHTLINE_USE_MOCK_LISTS=false
SIGHTLINE_ENABLE_LIST_UPDATES=false
SIGHTLINE_ENABLE_AI_EXPLANATIONS=false
```

Required Slack scopes
---------------------

Bot scopes:

- `app_home:read`
- `chat:write`

User scopes:

- `search:read` (required for live RTS search)

OAuth setup for RTS live search
-------------------------------

1. Start the app and open `http://127.0.0.1:5001/slack/oauth/authorize`.
   - The short alias `http://127.0.0.1:5001/authorize` is also supported.
2. Complete Slack OAuth consent for `search:read`.
3. Confirm a local token file is created at `SIGHTLINE_TOKEN_STORE_PATH`.
4. Trigger a real list context event; RTS searches will use the OAuth user token.

GitHub live evidence
--------------------

Set `GITHUB_TOKEN` to enable live REST lookups for GitHub issue and PR URLs found in Slack List rows. When configured, live GitHub state wins over embedded/mock metadata. If the API is unavailable or rate-limited, Sightline logs a clear warning and falls back to metadata when available.

Demo Mode
---------

Set `SIGHTLINE_USE_MOCK_LISTS=true` for hackathon judging if Slack Lists API access returns `list_not_found`. In mock mode, Sightline loads deterministic demo tasks and the Update button completes without calling Slack Lists update APIs.

Keep `SIGHTLINE_ENABLE_AI_EXPLANATIONS=false` for the fastest live demo. When it is false, Sightline still posts a deterministic explanation and does not wait on Gemini.

Deployment
----------

Docker:

```powershell
docker compose up --build
```

Production notes:

- Keep `.env` out of git.
- Use least-privilege Slack scopes.
- Enable `SIGHTLINE_ENABLE_LIST_UPDATES=true` only after validating the Slack Lists update payload in the target workspace.
- Keep `SIGHTLINE_USE_MOCK_LISTS=false` for the real recording so Slack Lists are loaded from the workspace.

Verification
------------

```powershell
python -m compileall app.py core handlers models services ui prompts
python -m unittest discover -s tests
```

Manual live checks for the final recording:

- OAuth: open `/authorize`, complete Slack consent, verify `.token_store.json` is created, then call `/api/health` and confirm `rts.userTokenPresent` is true.
- RTS: trigger a Slack List row whose title or GitHub reference appears in a real Slack message and confirm the card evidence includes the Slack search result.
- GitHub: reference a real issue or PR URL and confirm the returned state matches GitHub in the browser.
- Slack Lists: with `SIGHTLINE_USE_MOCK_LISTS=false`, click Update on a real card and confirm the row changes only when `SIGHTLINE_ENABLE_LIST_UPDATES=true`.
- Silence proof: open a non-stale row and confirm no Slack message is posted.
