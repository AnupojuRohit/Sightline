import json


def handle_context_change(event, logger):
    logger.info("APP CONTEXT CHANGED")

    print("\n" + "=" * 80)
    print("APP CONTEXT CHANGED")
    print("=" * 80)

    print(json.dumps(event, indent=2))

    context = event.get("context", {})
    entities = context.get("entities", [])

    print("\nEntities:")

    for i, entity in enumerate(entities):
        print(f"\nEntity {i + 1}")
        print(json.dumps(entity, indent=2))