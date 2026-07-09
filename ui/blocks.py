from models.analysis import Analysis


def build_analysis_blocks(analysis: Analysis, report: str):

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Sightline Analysis"
            }
        },

        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Health Score*\n{analysis.health_score}/100"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Total Tasks*\n{analysis.total_tasks}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Overdue*\n{analysis.overdue_tasks}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Blocked*\n{analysis.blocked_tasks}"
                },
            ]
        },

        {
            "type": "divider"
        },

        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": report[:2900]
            }
        },

        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🔄 Analyze Again"
                    },
                    "action_id": "analyze_again"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📋 Generate Plan"
                    },
                    "action_id": "generate_plan"
                }
            ]
        }
    ]