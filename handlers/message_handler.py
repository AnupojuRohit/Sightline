def handle_message(event, logger):
    logger.debug("message_event_ignored", extra={"event_type": event.get("type")})
