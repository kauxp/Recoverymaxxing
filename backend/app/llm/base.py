from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):

    @abstractmethod
    def generate_explanation(
        self,
        context: dict[str, Any]
    ) -> str:
        pass

    @abstractmethod
    def generate_customer_message(
        self,
        context: dict[str, Any]
    ) -> str:
        pass