from google import genai

from app.config import settings
from app.llm.base import LLMProvider


class GeminiProvider(LLMProvider):

    def __init__(self):
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )

    def generate_explanation(
        self,
        context: dict
    ) -> str:

        prompt = f"""
You are explaining a revenue recovery decision.

Event:
{context}

Explain:
1. What happened
2. Why the system selected this action
3. Why the action is safe
4. What stopping rule applies

Keep the explanation concise and factual.
Do not invent information.
"""

        response = self.client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt
        )

        return response.text

    def generate_customer_message(
        self,
        context: dict
    ) -> str:

        prompt = f"""
Write a short, polite payment recovery message.

Context:
{context}

Do not threaten the customer.
Do not claim payment succeeded unless the context says so.
"""

        response = self.client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt
        )

        return response.text