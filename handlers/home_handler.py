import json

from services.mock_loader import load_mock_tasks
from services.analyzer import Analyzer
from services.gemini_service import GeminiService
from ui.blocks import build_analysis_blocks

def handle_home(event, client, logger):

    logger.info("APP HOME OPENED")

    print(json.dumps(event, indent=2))

    tasks = load_mock_tasks()

    analysis = Analyzer().analyze(tasks)

    report = GeminiService().analyze(analysis)

   

    client.chat_postMessage(
        channel=event["channel"],
        text="Sightline Analysis",
        blocks=build_analysis_blocks(
            analysis,
            report
        )
    )
