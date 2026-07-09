import os

from dotenv import load_dotenv
from slack_bolt import App

load_dotenv()

app = App(
    token=os.getenv("SLACK_BOT_TOKEN")
)