from abc import ABC, abstractmethod
from typing import Any
from psalm.models.config import CaseInput


class BasePhase(ABC):
    @abstractmethod
    async def run(self, case_input: CaseInput) -> Any: ...
