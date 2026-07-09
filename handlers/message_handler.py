import json


def handle_message(event, logger):
    logger.info("MESSAGE EVENT")

    print("\n===== MESSAGE EVENT =====")
    print(json.dumps(event, indent=2))