from app.llm.factory import LLMFactory


class LLMExplainer:

    def __init__(self):
        self.llm = LLMFactory.create()

    def explain(
        self,
        event: dict
    ) -> str:

        return self.llm.generate_explanation(event)

    def customer_message(
        self,
        event: dict
    ) -> str:

        return self.llm.generate_customer_message(event)