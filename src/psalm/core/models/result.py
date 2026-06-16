from typing import Optional, Any

from pydantic import BaseModel, Field
from datetime import datetime
from psalm.core.models.books import Book
from psalm.core.models.anonymous_text import AnonymousText


class Result(BaseModel):
    """
    Represents the evaluation result for a book and its associated text.

    The Result class is used to store details about the evaluation process,
    including the book being evaluated, the evaluator's assessment, and any
    additional metadata. This encapsulated design provides a structured way
    to represent and handle evaluation data.

    :ivar source: The source book.
    :type source: Book
    :ivar target: The target text.
    :type target: AnonymousText
    :ivar evaluator: The evaluator used.
    :type evaluator: str
    :ivar score: The score given by the evaluator.
    :type score: float
    :ivar reason: The reason given by the evaluator for the score.
    :type reason: Optional[str]
    :ivar confidence: The confidence given by the evaluator for the score.
    :type confidence: Optional[float]
    :ivar timestamp: The timestamp of the evaluation.
    :type timestamp: datetime
    :ivar details: Additional details about the evaluation.
    :type details: Optional[dict[str, Any]]
    """
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