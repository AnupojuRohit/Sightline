import os

from slack_sdk import WebClient


client = WebClient(
    token=os.environ["SLACK_BOT_TOKEN"]
)