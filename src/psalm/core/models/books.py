from pydantic import BaseModel, Field


class Book(BaseModel):
    title: str = Field(
        description="Title of the book."
    )
    author: str = Field(
        description="Author of the book."
    )
    text: str = Field(
        description="Text of the book."
    )
    language: str = Field(
        description="Language of the book."
    )

class BookTranslations(BaseModel):
    original: Book = Field(
        description="Original book."
    )
    translations: list[Book] = Field(
        description="List of books with translations."
    )