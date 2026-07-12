import os

from dotenv import load_dotenv
from slack_bolt import App

load_dotenv()

_bolt_oauth_env = {
    "SLACK_CLIENT_ID": os.environ.pop("SLACK_CLIENT_ID", None),
    "SLACK_CLIENT_SECRET": os.environ.pop("SLACK_CLIENT_SECRET", None),
}
try:
    app = App(
        token=os.getenv("SLACK_BOT_TOKEN"),
        token_verification_enabled=os.getenv("SLACK_AUTH_TEST_ON_STARTUP", "false").lower() == "true",
    )
finally:
    for _name, _value in _bolt_oauth_env.items():
        if _value is not None:
            os.environ[_name] = _value
