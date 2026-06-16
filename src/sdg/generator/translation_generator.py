from langchain_text_splitters import RecursiveCharacterTextSplitter

from sdg.configs import ModelConfig
from sdg.configs.generators import TranslatorGeneratorConfig
from sdg.models.open_ai_model import OpenAIModel
from sdg.validations import TranslatedText


class TranslationGenerator:
    def __init__(self, translator_config: TranslatorGeneratorConfig, model_config: ModelConfig):
        self._translator_config = translator_config
        self._model_config = model_config
        self.model = OpenAIModel(model_config)

    def generate_with_splitting(self, text: str, chunk_size: int = 10000) -> TranslatedText:
        chunks = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0, separators=["\n\n\n", "\n\n", "\n"]).split_text(text)

        final_text = ""
        for chunk in chunks:
            merged_text = self.format_prompt(chunk)
            output = self.model.generate(
                instruction=merged_text,
                structure=TranslatedText
            )

            final_text += output.translated_text

        return TranslatedText(translated_text=final_text)

    def generate(self, text: str) -> TranslatedText:
        merged_text = self.format_prompt(text)

        output = self.model.generate(
            instruction=merged_text,
            structure=TranslatedText
        )

        if output is None:
            raise ValueError("No output generated.")

        return output

    async def a_generate(self, text: str) -> TranslatedText:
        merged_text = self.format_prompt(text)

        output = await self.model.a_generate(
            instruction=merged_text,
            structure=TranslatedText
        )

        if output is None:
            raise ValueError("No output generated.")

        return output

    async def batch(self, texts: list[str]) -> list[TranslatedText]:
        merged_texts = [self.format_prompt(text) for text in texts]

        outputs = await self.model.batch(
            instructions=merged_texts,
            structure=TranslatedText
        )

        return outputs

    def format_prompt(self, text: str) -> str:
        return f"""
        {self.instruction()}

        Text:
        \"\"\"
        {text}
        \"\"\"
        """

    def instruction(self) -> str:
        return self._translator_config.instruction.replace("{language}", self._translator_config.language)
