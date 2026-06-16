from pydantic import BaseModel, Field


class Book(BaseModel):
    """
    Represents a book with its title, author, text, and language.

    This class is used to model a book, encapsulating its title,
    the author's name, the main textual content, and the language
    in which the book is presented.

    :ivar title: Title of the book.
    :type title: str
    :ivar author: Author of the book.
    :type author: str
    :ivar text: Text of the book.
    :type text: str
    :ivar language: Language of the book.
    :type language: str
    """
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