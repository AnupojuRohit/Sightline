import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


class GeminiService:

    def analyze(self, analysis):

        prompt = f"""
You are Sightline AI.

You are an elite Engineering Manager.

Project Health Score:
{analysis.health_score}/100

Statistics
----------
Total Tasks: {analysis.total_tasks}
Overdue: {analysis.overdue_tasks}
Blocked: {analysis.blocked_tasks}
Unassigned: {analysis.unassigned_tasks}

Detected Risks
--------------
{analysis.risks}

Generate a Slack report.

Return Markdown.

Sections:

# Executive Summary

# Critical Risks

# Recommended Actions

# Overall Status
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        return response.text