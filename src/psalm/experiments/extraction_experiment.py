import os
from pathlib import Path
from typing import Optional
import unsloth
import polars as pl
from rich.console import Console
from rich.progress import track
from rich.status import Status

from psalm.configs.experiments import ExtractionExperimentConfig
from psalm.datasets.unlearning_dataset import build_unlearning_train_dataset
from psalm.models import HuggingFaceModel
from psalm.models.chat_templates.unsloth_qa_chat_template import UnslothQAChatTemplate


class ExtractionExperiment:
    def __init__(self, config: ExtractionExperimentConfig):
        self._config = config
        self._console = Console()

    def execute(self):
        self._console.rule("PSALM Extraction Experiments")
        save_to = self._config.save.save_to
        if isinstance(save_to, str):
            save_to = Path(save_to)

        # Create parent directories if they don't exist'
        save_to.parent.mkdir(parents=True, exist_ok=True)

        hf_model_instance = HuggingFaceModel(self._config.inference_config.model, self._config.inference_config.lora)
        chat_template_instance = UnslothQAChatTemplate(self._config.inference_config.chat_template, hf_model_instance)
        hf_model_instance = chat_template_instance.load()

        dataset = build_unlearning_train_dataset(
            self._config.dataset,
            forget_split=self._config.npo.forget_split,
            retain_split=self._config.npo.retain_split,
            chat_template=chat_template_instance,
            dataset_text_field=self._config.dataset_text_field,
        )

        df = dataset.shuffle(seed=self._config.random_state).to_polars()

        forget_samples = []
        retain_samples = []

        n_samples = self._config.n_samples

        with Status("Extracting Answer from LLM", console=self._console, spinner="monkey") as status:
            for row in track(df.iter_rows(named=True), total=len(df), description="Extracting..."):
                is_forget = row["is_forget"]
                ti_id = row["ti_id"]
                question = row["question"]

                status.update(f"Extracting Answers for {ti_id} ({'forget' if is_forget else 'retain'}): {question} ")

                # Check if all n samples per set has been retrieved
                if len(forget_samples) > n_samples and len(retain_samples) > n_samples:
                    break

                if is_forget and len(forget_samples) <= n_samples:
                    self._console.print(f"Extracting Forget: {ti_id}: {question}")
                    item = self.inference_call(
                        row, hf_model_instance, chat_template_instance
                    )

                    if item is None:
                        continue

                    self._console.print("Add Item to Forget")

                    forget_samples.append(item)
                elif not is_forget and len(retain_samples) <= n_samples:
                    self._console.print(f"Extracting Retain: {ti_id}: {question}")
                    item = self.inference_call(
                        row, hf_model_instance, chat_template_instance
                    )

                    if item is None:
                        continue

                    self._console.print("Add Item to Retain")

                    retain_samples.append(item)

            status.update(f"Finished Extracing Answers, combining into a single DataFrame...")

            forget_rows = [{**item, "is_forget": True} for item in forget_samples]
            retain_rows = [{**item, "is_forget": False} for item in retain_samples]

            # (Optional) reorder columns for readability
            desired_cols = [
                "ti_id",
                "author",
                "is_forget",
                "question",
                "expected_answer",
                "actual_answer",
            ]

            if not forget_rows and not retain_rows:
                status.update("Both Forget and Retain Datasets seem to be empty.")
                combined_df = pl.DataFrame(
                    schema=desired_cols
                )
            else:
                # Combine and build a single DataFrame
                combined_df = pl.DataFrame(forget_rows + retain_rows)


                combined_df = combined_df.select([c for c in desired_cols if c in combined_df.columns] +
                                                 [c for c in combined_df.columns if c not in desired_cols])

                status.update(f"Extracted {len(combined_df)} questions...")

            status.update(f"Saving DataFrame")
            combined_df.write_parquet(save_to)
            self._console.rule(f"Extracted Dataset Saved to {save_to.absolute().as_posix()}")

    def inference_call(self, row: dict, hf_model_instance: HuggingFaceModel, chat_template_instance: UnslothQAChatTemplate) -> Optional[dict]:
        question = row["question"]
        expected_answer = row["answer"]
        ti_id = row["ti_id"]
        author = row["author"]

        found_answer = None
        max_retries = 3

        for idx in track(range(max_retries), total=max_retries):
            try:
                response = hf_model_instance.inference([
                    {"role": "user", "content": question}
                ], chat_template_instance, self._config.inference_config)

                # Get message with role "assistant"
                for item in response:
                    if item["role"] == "assistant":
                        found_answer = item["content"]
                        break

                if found_answer is not None:
                    break
            except Exception as e:
                self._console.print(f"[red]ERROR[/red]: {str(e)}")
                found_answer = None

        if found_answer is None:
            return None

        item = {
            "ti_id": ti_id,
            "author": author,
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": found_answer,
        }

        return item
