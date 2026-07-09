from prompts.risk_prompt import SYSTEM_PROMPT


class AIService:

    def generate(self, score, risks):

        prompt = f"""
{SYSTEM_PROMPT}

Health Score:
{score}

Risks:
{risks}
"""

        return prompt