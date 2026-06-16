from typing import TypeVar, Union, Any, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from sdg.configs import ModelConfig

from rich.console import Console

console = Console()

class OpenAIModel:
    def __init__(self, model_config: ModelConfig):
        self._model_config = model_config
        self.model: ChatOpenAI = self.load()

    def load(self) -> ChatOpenAI:

        return ChatOpenAI(
            model=self._model_config.model_name,
            temperature=self._model_config.temperature,
            top_p=self._model_config.top_p,
            reasoning_effort=self._model_config.reasoning_effort,
            max_tokens=self._model_config.max_tokens,
            timeout=self._model_config.timeout,
            max_retries=self._model_config.max_retries,
            base_url=self._model_config.base_url,
            organization=self._model_config.organization,
        )

    _BM = TypeVar("_BM", bound=BaseModel)
    _DictOrPydanticClass = Union[dict[str, Any], type[_BM], type]
    def generate(self, instruction: str, structure: Optional[_DictOrPydanticClass]) -> Optional[_DictOrPydanticClass]:
        self.precheck(structure)

        model_with_structured_output = self.model.with_structured_output(structure)
        response = model_with_structured_output.invoke(instruction)

        output = structure.model_validate(response)

        return output

    async def a_generate(self, instruction: str, structure: Optional[_DictOrPydanticClass]) -> Optional[_DictOrPydanticClass]:
        self.precheck(structure)

        model_with_structured_output = self.model.with_structured_output(structure)
        response = await model_with_structured_output.ainvoke(instruction)

        output = structure.model_validate(response)

        return output

    async def batch(self, instructions: list[str], structure: Optional[_DictOrPydanticClass]) -> list[Optional[_DictOrPydanticClass]]:
        self.precheck(structure)

        model_with_structured_output = self.model.with_structured_output(structure)
        response = await model_with_structured_output.abatch(instructions)

        return response

    def precheck(self, structure: Optional[_DictOrPydanticClass]):
        if structure is None:
            raise ValueError("structure must be provided")

        if self.model is None:
            self.model = self.load()