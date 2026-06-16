from dataclasses import replace
from typing import Optional

from datasets import Dataset, concatenate_datasets
from rich.console import Console
from rich.status import Status

from psalm.configs.datasets.dataset_config import DatasetConfig
from psalm.datasets.huggingface_dataset import HuggingFaceDataset
from psalm.models.chat_templates.unsloth_qa_chat_template import UnslothQAChatTemplate

console = Console()


def _clone_with_split(cfg: DatasetConfig, split: str) -> DatasetConfig:
    return replace(cfg, split=split)


def build_unlearning_train_dataset(
    base_dataset_cfg: DatasetConfig,
    forget_split: str,
    retain_split: Optional[str],
    chat_template: UnslothQAChatTemplate,
    dataset_text_field: str = "text",
    question_column: str = "question",
    answer_column: str = "answer",
) -> Dataset:
    """
    Build a dataset with combined forget and retain examples, and an 'is_forget'
    column (1 for forget, 0 for retain). Assumes QA columns with defaults
    'question' and 'answer'; extra columns (e.g., ti_id, author) are preserved.
    """
    with Status("Loading unlearning datasets", spinner="monkey"):
        # Forget
        forget_cfg = _clone_with_split(base_dataset_cfg, forget_split)
        forget_hf = HuggingFaceDataset(forget_cfg)
        forget_hf.format(
            chat_template,
            tokenize=False,
            add_generation_prompt=False,
            return_only=False,
            return_column=dataset_text_field,
            question_column=question_column,
            answer_column=answer_column,
        )
        forget_ds = forget_hf.dataset.add_column("is_forget", [1] * len(forget_hf.dataset))

        # Retain (optional)
        if retain_split is not None:
            retain_cfg = _clone_with_split(base_dataset_cfg, retain_split)
            retain_hf = HuggingFaceDataset(retain_cfg)
            retain_hf.format(
                chat_template,
                tokenize=False,
                add_generation_prompt=False,
                return_only=False,
                return_column=dataset_text_field,
                question_column=question_column,
                answer_column=answer_column,
            )
            retain_ds = retain_hf.dataset.add_column("is_forget", [0] * len(retain_hf.dataset))
            combined = concatenate_datasets([forget_ds, retain_ds])
        else:
            combined = forget_ds

    return combined