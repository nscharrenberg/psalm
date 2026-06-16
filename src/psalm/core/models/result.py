from typing import Optional, Any

from pydantic import BaseModel, Field
from datetime import datetime
from psalm.core.models.books import Book
from psalm.core.models.anonymous_text import AnonymousText


class Result(BaseModel):
    source: Book = Field(
        description="The source book."
    )

    target: AnonymousText = Field(
        description="The target text."
    )

    evaluator: str = Field(
        description="The evaluator used."
    )

    score: float = Field(
        description="The score given by the evaluator."
    )

    reason: Optional[str] = Field(
        description="The reason given by the evaluator for the score."
    )

    confidence: Optional[float] = Field(
        default=None,
        description="The confidence given by the evaluator for the score."
    )

    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="The timestamp of the evaluation."
    )

    details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional details about the evaluation."
    )