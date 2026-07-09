from services.slack_client import client


def get_list_items(list_id: str):
    response = client.api_call(
        api_method="slackLists.items.list",
        json={
            "list_id": list_id
        }
    )

    return response