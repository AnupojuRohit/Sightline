import logging
import os
from threading import Thread

from slack_bolt.adapter.socket_mode import SocketModeHandler

from core.bolt_app import app
from dashboard_app import create_server

from handlers.button_handler import handle_dismiss_task, handle_update_task
from handlers.context_handler import handle_context_change
from handlers.home_handler import handle_home
from handlers.message_handler import handle_message
from services.slack_oauth import log_oauth_startup_status
from ui.blocks import DISMISS_TASK_ACTION_ID, UPDATE_TASK_ACTION_ID

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


@app.event("app_context_changed")
def context_changed(event, client, logger):
    handle_context_change(event, client, logger)

@app.event("app_home_opened")
def app_home(event, client, logger):
    handle_home(event, client, logger)


@app.event("message")
def message(event, logger):
    handle_message(event, logger)


@app.action(UPDATE_TASK_ACTION_ID)
def update_task_action(ack, body, client, logger):
    handle_update_task(ack, body, client, logger)


@app.action(DISMISS_TASK_ACTION_ID)
def dismiss_task_action(ack, body, client, logger):
    handle_dismiss_task(ack, body, client, logger)


if __name__ == "__main__":
    print("=" * 50)
    print("Sightline")
    print("=" * 50)

    log_oauth_startup_status()

    dashboard_server = create_server()
    Thread(target=dashboard_server.serve_forever, daemon=True).start()

    SocketModeHandler(
        app,
        os.environ["SLACK_APP_TOKEN"]
    ).start()
