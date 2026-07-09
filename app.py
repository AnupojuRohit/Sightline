import logging
import os

from slack_bolt.adapter.socket_mode import SocketModeHandler

from core.bolt_app import app

from handlers.context_handler import handle_context_change
from handlers.home_handler import handle_home
from handlers.message_handler import handle_message

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


@app.event("app_context_changed")
def context_changed(event, logger):
    handle_context_change(event, logger)

@app.event("app_home_opened")
def app_home(event, client, logger):
    handle_home(event, client, logger)


@app.event("message")
def message(event, logger):
    handle_message(event, logger)


if __name__ == "__main__":
    print("=" * 50)
    print("Sightline")
    print("=" * 50)

    SocketModeHandler(
        app,
        os.environ["SLACK_APP_TOKEN"]
    ).start()