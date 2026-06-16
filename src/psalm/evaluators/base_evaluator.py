from abc import ABC, abstractmethod
import threading

from psalm.core.models import Book, AnonymousText, Result


class BaseEvaluator(ABC):
    def __init__(self):
        self._lock = threading.Lock()

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def description(cls) -> str:
        pass

    @abstractmethod
    def evaluate(self, source: Book, target: AnonymousText, **kwargs) -> Result:
        pass

    @abstractmethod
    async def a_evaluate(self, source: Book, target: AnonymousText, **kwargs) -> Result:
        pass

    @staticmethod
    def compute_confidence(score: float) -> float:
        return abs(score - 0.5) * 2.0