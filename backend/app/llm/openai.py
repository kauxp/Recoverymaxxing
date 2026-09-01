from openai import OpenAI

from app.config import settings
from app.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY
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

        response = self.client.responses.create(
            model=settings.OPENAI_MODEL,
            input=prompt
        )

        return response.output_text

    def generate_customer_message(
        self,
        context: dict
    ) -> str:

        prompt = f"""
Create a short and polite payment recovery message.

Context:
{context}

Do not claim the payment succeeded unless explicitly stated.
"""

        response = self.client.responses.create(
            model=settings.OPENAI_MODEL,
            input=prompt
        )

        return response.output_text