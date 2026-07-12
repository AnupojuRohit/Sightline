from ui.blocks import build_home_blocks


def handle_home(event, client, logger):
    logger.info("APP HOME OPENED")

    client.views_publish(
        user_id=event["user"],
        view={
            "type": "home",
            "blocks": build_home_blocks(),
        },
    )
