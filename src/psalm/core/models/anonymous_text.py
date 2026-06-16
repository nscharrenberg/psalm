from pydantic import BaseModel, Field


class AnonymousText(BaseModel):
    """
    Represents a model for anonymized text data.

    This class serves as a structure for handling and validating serialized
    text data. It ensures the data adheres to the defined standards and provides
    an interface for manipulation or interaction with text fields.

    :ivar text: The textual content for the model.
    :type text: str
    """
    text: str = Field(
        description="The text."
    )