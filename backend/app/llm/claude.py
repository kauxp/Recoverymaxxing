from anthropic import Anthropic

from app.config import settings
from app.llm.base import LLMProvider


class ClaudeProvider(LLMProvider):

    def __init__(self):
        self.client = Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    def generate_explanation(
        self,
        context: dict
    ) -> str:

        prompt = f"""
Explain this revenue recovery decision.

Context:
{context}

Explain:
1. What happened
2. Why this action was selected
3. Why it is safe
4. What stopping rule applies

Be concise and do not invent facts.
"""

        response = self.client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.content[0].text

    def generate_customer_message(
        self,
        context: dict
    ) -> str:

        prompt = f"""
Write a short, polite payment recovery message.

Context:
{context}

Do not claim the payment succeeded unless explicitly stated.
"""

        response = self.client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.content[0].text