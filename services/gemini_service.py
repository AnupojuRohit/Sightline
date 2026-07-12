import os
import logging

from dotenv import load_dotenv

try:
    from google import genai
except ImportError:
    genai = None

from models.mismatch import Mismatch

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) if genai is not None else None

logger = logging.getLogger(__name__)


class GeminiService:

    def analyze(self, analysis):
        if client is None:
            return "Gemini SDK is not installed. Sightline deterministic checks are still available."

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

    def explain_mismatch(self, mismatch: Mismatch) -> str:
        if not self._ai_explanations_enabled() or client is None or not os.getenv("GEMINI_API_KEY"):
            return "Deterministic rules found source-of-truth evidence that conflicts with the Slack List status."

        evidence = self._evidence_summary(mismatch)
        prompt = f"""
You are Sightline.

Explain this deterministic stale-task finding in one concise Slack sentence.
Do not add new evidence. Do not guess. Do not decide whether it is stale.

Task: {mismatch.task.title}
Current Slack List status: {mismatch.task.status}
Recommended status: {mismatch.recommended_status}
Rule result: {mismatch.reason}
Evidence:
{evidence}
"""

        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
            )
        except Exception:
            logger.exception("gemini_mismatch_explanation_failed", extra={"task_id": mismatch.task.id})
            return "Deterministic rules found source-of-truth evidence that conflicts with the Slack List status."

        return (response.text or "").strip()[:300]

    def _ai_explanations_enabled(self) -> bool:
        return os.getenv("SIGHTLINE_ENABLE_AI_EXPLANATIONS", "false").strip().lower() in {"1", "true", "yes", "on"}

    def _evidence_summary(self, mismatch: Mismatch) -> str:
        lines: list[str] = []

        for github_state in mismatch.evidence.github:
            reference = github_state.reference
            state = "merged" if github_state.merged else github_state.state
            lines.append(f"- GitHub {reference.kind} #{reference.number}: {state}")

        for rts_evidence in mismatch.evidence.rts:
            lines.append(f"- Slack search: {rts_evidence.text[:160]}")

        return "\n".join(lines) if lines else "- No additional evidence text available."
