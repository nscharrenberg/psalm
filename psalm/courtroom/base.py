from abc import ABC, abstractmethod
from psalm.models.config import CaseInput
from psalm.models.result import PSALMResult


class CourtroomSetup(ABC):
    @abstractmethod
    async def run(self, case_input: CaseInput) -> PSALMResult: ...
