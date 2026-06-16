from rich.console import Console
from datasets import Dataset, load_dataset
from rich.status import Status

from psalm.configs import DatasetConfig
from psalm.models.chat_templates.unsloth_chat_template import UnslothChatTemplate

console = Console()

class HuggingFaceDataset:
    def __init__(self, dataset_config: DatasetConfig):
        self._dataset_config = dataset_config
        self.dataset: Dataset = self.load()

    def load(self):
        with Status("Loading dataset from HuggingFace", spinner="monkey"):
            return load_dataset(
                path=self._dataset_config.path,
                name=self._dataset_config.subset,
                split=self._dataset_config.split,
                data_dir=self._dataset_config.data_dir,
                data_files=self._dataset_config.data_files,
                cache_dir=self._dataset_config.cache_dir,
                features=self._dataset_config.features,
                num_proc=self._dataset_config.num_proc,
                streaming=self._dataset_config.streaming,
            )

    def format(self, chat_template: UnslothChatTemplate, tokenize: bool = False, add_generation_prompt: bool = False, return_only: bool = False, **kwargs) -> Dataset:
        """
        Formats the dataset using the `UnslothChatTemplate` object and applies certain
        operations based on the provided parameters. This method optionally updates the
        current dataset object and returns the processed dataset.

        Args:
            chat_template (UnslothChatTemplate): Template instance for applying formatting to the dataset.
            tokenize (bool, optional): If True, tokenizes the dataset during formatting. Defaults to False.
            add_generation_prompt (bool, optional): If True, adds a generation prompt while formatting.
                Defaults to False.
            return_only (bool, optional): If True, only returns the processed dataset without modifying
                the internal dataset. Defaults to False.
            **kwargs: Additional keyword arguments forwarded to the template's apply method.

        Returns:
            Dataset: The processed dataset after applying the formatting.
        """
        with Status("Formatting dataset", spinner="monkey"):
            dataset = self.dataset.map(lambda x: chat_template.apply(x, tokenize=tokenize, add_generation_prompt=add_generation_prompt, **kwargs), batched=True)

            if not return_only:
                self.dataset = dataset

            return dataset