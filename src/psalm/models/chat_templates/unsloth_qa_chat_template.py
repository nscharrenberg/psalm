from typing import Any

from rich.status import Status
from psalm.models.chat_templates.unsloth_chat_template import UnslothChatTemplate


class UnslothQAChatTemplate(UnslothChatTemplate):
    def apply_chat_template(self, messages: list[dict[str, str]], tokenize: bool = False, add_generation_prompt: bool = False, **kwargs):
        return self._model_instance.tokenizer.apply_chat_template(
            messages,
            tokenize=tokenize,
            add_generation_prompt=add_generation_prompt,
            **kwargs
        )

    def apply(self, examples, tokenize: bool = False, add_generation_prompt: bool = False, **kwargs) -> dict[str, Any]:
        """
        Formats input examples into a structured conversation chat format using specified
        question, answer, and return columns. Users can customize the columns for questions,
        answers, and return values, as well as control tokenization and addition of a
        generation prompt.

        Args:
            examples (dict): Dictionary containing the input data with keys corresponding
                to columns used for questions, answers, and other data.
            tokenize (bool, optional): Specifies whether to tokenize the generated chat
                texts. Defaults to False.
            add_generation_prompt (bool, optional): Specifies whether to include a
                generation prompt in the chat texts. Defaults to False.
            **kwargs: Additional keyword arguments to customize column names:
                - 'question_column' (str): Column name for questions. Defaults to "question".
                - 'answer_column' (str): Column name for answers. Defaults to "answer".
                - 'return_column' (str): Column name for the output. Defaults to "prompt".

        Returns:
            dict: A dictionary with the specified return_column key containing a list of
                formatted chat texts based on the input examples.
        """
        with Status("Formatting Unsloth QA Chat Template"):
            if "question_column" in kwargs:
                question_column = kwargs["question_column"]
            else:
                question_column = "question"

            if "answer_column" in kwargs:
                answer_column = kwargs["answer_column"]
            else:
                answer_column = "answer"

            if "return_column" in kwargs:
                return_column = kwargs["return_column"]
            else:
                return_column = "text"

            question = examples[question_column]
            answers = examples[answer_column]

            qa_chats = []
            for q, a in zip(question, answers):
                messages = [
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a},
                ]

                text = self.apply_chat_template(messages, tokenize=tokenize, add_generation_prompt=add_generation_prompt)

                qa_chats.append(text)

            return {
                return_column: qa_chats
            }