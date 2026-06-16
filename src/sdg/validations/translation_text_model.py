from pydantic import BaseModel, Field


class TranslatedText(BaseModel):
    translated_text: str = Field(
        description="The translated text."
    )