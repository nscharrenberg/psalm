from langchain_text_splitters import RecursiveCharacterTextSplitter
from rich.progress import track

from psalm.core.models import Book
from sdg.configs import ModelConfig
from sdg.configs.generators import QuestionVerbatimAnswerGeneratorConfig
from sdg.models.open_ai_model import OpenAIModel
from sdg.validations import VerbatimQAList, VerbatimQAItem


class QuestionVerbatimAnswerGenerator:
    def __init__(self, config: QuestionVerbatimAnswerGeneratorConfig, model_config: ModelConfig):
        self._config = config
        self._model_config = model_config
        self.model = OpenAIModel(model_config)

    def generate_with_splitting(self, book: Book, chunk_size: int = 10000) -> VerbatimQAList:
        chunks = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0, separators=["\n\n\n", "\n\n", "\n"]).split_text(book.text)

        merged_qa_list: list[VerbatimQAItem] = []
        for chunk in track(chunks, total=len(chunks), description="Chunks..."):
            temp_book = Book(title=book.title, author=book.author, text=chunk, language=book.language)
            merged_text = self.format_prompt(temp_book)
            output = self.model.generate(
                instruction=merged_text,
                structure=VerbatimQAList
            )

            merged_qa_list.extend(output.items)

        return VerbatimQAList(items=merged_qa_list)

    def generate(self, book: Book) -> VerbatimQAList:
        merged_text = self.format_prompt(book)

        output = self.model.generate(
            instruction=merged_text,
            structure=VerbatimQAList
        )

        if output is None:
            raise ValueError("No output generated.")

        return output

    async def a_generate(self, book: Book) -> VerbatimQAList:
        merged_text = self.format_prompt(book)

        output = await self.model.a_generate(
            instruction=merged_text,
            structure=VerbatimQAList
        )

        if output is None:
            raise ValueError("No output generated.")

        return output

    async def batch(self, books: list[Book]) -> list[VerbatimQAList]:
        merged_texts = [self.format_prompt(book) for book in books]

        outputs = await self.model.batch(
            instructions=merged_texts,
            structure=VerbatimQAList
        )

        return outputs

    def format_prompt(self, book: Book) -> str:
        return f"""
        {self.instruction(book)}

        Text:
        \"\"\"
        {book.text}
        \"\"\"
        
        {self.min_max_instruction()}
        """

    def min_max_instruction(self):
        if self._config.max_amount_of_questions_per_book is None:
            return f"""
            Produce a minimum of {self._config.min_amount_of_questions_per_book} QA items depending on content density.
            """

        return f"""
        Produce between {self._config.min_amount_of_questions_per_book} and {self._config.max_amount_of_questions_per_book} QA items depending on content density.
        """


    def instruction(self, book: Book) -> str:
        return self._config.instruction.replace("{book_title}", book.title).replace("{book_author}", book.author)
