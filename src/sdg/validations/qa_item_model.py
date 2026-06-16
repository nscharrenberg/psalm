from pydantic import BaseModel, Field


class VerbatimQAItem(BaseModel):
    question: str = Field(
        description="Question that explicitly mentions the book title and author."
    )
    answer: str = Field(
        description="Verbatim excerpt from the text, contiguous, ≤1024 chars."
    )
    start_char: int = Field(
        description="0-based start index into the provided Text."
    )
    end_char: int = Field(
        description="0-based end index (exclusive) into the Text."
    )