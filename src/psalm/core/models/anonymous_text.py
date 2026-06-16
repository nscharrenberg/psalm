from pydantic import BaseModel, Field


class AnonymousText(BaseModel):
    text: str = Field(
        description="The text."
    )