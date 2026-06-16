import typing
from typing import Any

from rich.status import Status
from unsloth import get_chat_template

from psalm.configs import ChatTemplateConfig

if typing.TYPE_CHECKING:
    from psalm.models.huggingface_model import HuggingFaceModel


class UnslothChatTemplate:
    def __init__(self, chat_template_config: ChatTemplateConfig, model_instance: "HuggingFaceModel"):
        self._chat_template_config = chat_template_config
        self._model_instance = model_instance

    def load(self) -> "HuggingFaceModel":
        """
        Loads and returns a chat template based on the current chat template configuration.

        This method utilizes a status spinner for visual feedback during the loading process.
        The chat template is created using configurations such as template definition, mapping,
        token EOS settings, and system message defined in the accompanying configuration.

        Returns:
            ChatTemplate: The generated chat template based on the provided configuration.
        """
        with Status("Loading Unsloth Chat Template", spinner="monkey"):
            tokenizer = get_chat_template(
                self._model_instance.tokenizer,
                chat_template=self._chat_template_config.chat_template,
                mapping=self._chat_template_config.mapping,
                map_eos_token=self._chat_template_config.map_eos_token,
                system_message=self._chat_template_config.system_message
            )

            self._model_instance.tokenizer = tokenizer

            return self._model_instance

    def apply_chat_template(self, messages: list[dict[str, str]], tokenize: bool = False,
                            add_generation_prompt: bool = False, **kwargs):
        raise NotImplementedError

    def apply(self, examples, **kwargs) -> dict[str, Any]:
        raise NotImplementedError