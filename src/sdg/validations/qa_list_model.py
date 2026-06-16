from pydantic import BaseModel, Field
from sdg.validations.qa_item_model import VerbatimQAItem


class VerbatimQAList(BaseModel):
    items: list[VerbatimQAItem] = Field(
        description="List of QA items with verbatim answers."
    )