from pydantic import BaseModel, Field

from psalm.core.models import AnonymousText, Book


class ControlDatasetVariantItem(BaseModel):
    text: AnonymousText = Field(
        description="The text of the control dataset variant."
    )
    expected_score: float = Field(
        description="The expected score of the control dataset variant."
    )
    text_similarity: str = Field(
        description="The expected similarity of the control dataset variant."
    )

class ControlDataset(BaseModel):
    control_case: str = Field(
        description="The name of the control case."
    )
    source: Book = Field(
        description="The source book."
    )
    variants: list[ControlDatasetVariantItem] = Field(
        description="List of control dataset variants."
    )