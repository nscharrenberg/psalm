from pathlib import Path
from typing import Union, Optional
import asyncio
import polars as pl
from psalm.core.models import Book, AnonymousText, Result
from psalm.evaluators.base_evaluator import BaseEvaluator
from psalm.evaluators.computational.lexical import (
    ExactMatchEvaluator,
    BleuEvaluator,
    RougeEvaluator,
)
from psalm.evaluators.llm.exceptions import (
    ParodySatireEvaluator,
    PasticheEvaluator,
    QuotationCitationEvaluator,
    ScenesAFaireEvaluator,
)
from psalm.evaluators.llm.narrative import (
    CharacterSimilarityEvaluator,
    PlotStructureSimilarityEvaluator,
    SceneSequenceSimilarityEvaluator,
    WorldBuildingSimilarityEvaluator,
)
from psalm.evaluators.llm.stylistic import (
    WritingStyleEvaluator,
    NarrativeVoiceEvaluator,
)
from rich.console import Console
from rich.progress import Progress, TaskID

from psalm.configs.experiments import (
    EvaluationExperimentConfig,
)


class EvaluationExperiment:
    def __init__(
        self,
        config: EvaluationExperimentConfig,
    ):
        self._config = config
        self._console = Console()
        self._max_concurrent = self._config.max_concurrent
        self._save_intermediate = self._config.save_intermediate
        self._checkpoint_frequency = self._config.checkpoint_frequency
        self._shuffle = self._config.shuffle
        self._seed = self._config.seed

    def execute(self):
        """Main entry point - runs async execution."""
        asyncio.run(self._execute_async())

    async def _execute_async(self):
        self._console.rule("PSALM Evaluation Experiments")
        self._console.print(f"   Data: {self._config.dataset_path}")
        save_to = self._config.save_dir
        if isinstance(save_to, str):
            save_to = Path(save_to)

        save_to.parent.mkdir(parents=True, exist_ok=True)

        dataset_path = self._config.dataset_path
        if isinstance(dataset_path, str):
            dataset_path = Path(dataset_path)

        if not dataset_path.exists():
            raise ValueError(
                f"Dataset Path at '{dataset_path.absolute().as_posix()}' "
                "does not exist"
            )

        df = pl.read_parquet(dataset_path)

        # Shuffle the dataframe if requested
        if self._shuffle:
            df = df.sample(fraction=1.0, shuffle=True, seed=self._seed)
            self._console.print(
                f"[bold cyan]Dataframe shuffled[/bold cyan]"
                + (f" (seed={self._seed})" if self._seed is not None else "")
            )

        # Initialize all evaluators
        evaluators = [
            ExactMatchEvaluator(),
            BleuEvaluator(),
            RougeEvaluator(),
            WritingStyleEvaluator(),
            NarrativeVoiceEvaluator(),
            CharacterSimilarityEvaluator(),
            PlotStructureSimilarityEvaluator(),
            SceneSequenceSimilarityEvaluator(),
            WorldBuildingSimilarityEvaluator(),
            ParodySatireEvaluator(),
            PasticheEvaluator(),
            QuotationCitationEvaluator(),
            ScenesAFaireEvaluator(),
        ]

        # Check for existing checkpoint and resume if available
        checkpoint_path = self._get_checkpoint_path(save_to)
        results, start_idx = self._load_checkpoint(checkpoint_path, df)

        # Process remaining rows (skip already processed ones)
        remaining_df = df[start_idx:]

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Processing rows...", total=len(df)
            )
            progress.update(task, completed=start_idx)

            for idx, row in enumerate(
                remaining_df.iter_rows(named=True), start=start_idx
            ):
                self._console.print(
                    f"[{idx + 1}/{len(df)}] Starting Evaluation for "
                    f"{row['question']}"
                )

                row_dict = await self._evaluate_row_async(
                    row, evaluators, progress
                )

                self._console.print(
                    f"[{idx + 1}/{len(df)}] Finished Evaluation for "
                    f"{row['question']}"
                )
                results.append(row_dict)
                progress.update(task, advance=1)

                # Save checkpoint periodically
                if self._save_intermediate and (
                    (idx + 1) % self._checkpoint_frequency == 0
                ):
                    self._save_checkpoint(results, checkpoint_path)
                    self._console.print(
                        f"[bold blue]Checkpoint saved:[/bold blue] "
                        f"{idx + 1}/{len(df)} rows completed"
                    )

        # Save final results
        results_df = pl.DataFrame(results)
        results_df.write_parquet(save_to)
        self._console.print(
            f"[bold green]Final results saved to:[/bold green] "
            f"{save_to.absolute().as_posix()}"
        )

        # Clean up checkpoint file
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            self._console.print(
                "[bold blue]Checkpoint file removed[/bold blue]"
            )

    def _get_checkpoint_path(self, save_to: Path) -> Path:
        """Generate checkpoint file path."""
        return save_to.parent / f"{save_to.stem}_checkpoint.parquet"

    def _load_checkpoint(
        self, checkpoint_path: Path, original_df: pl.DataFrame
    ) -> tuple[list[dict], int]:
        """Load checkpoint if it exists, otherwise return empty results."""
        if checkpoint_path.exists():
            try:
                checkpoint_df = pl.read_parquet(checkpoint_path)
                results = checkpoint_df.to_dicts()
                start_idx = len(results)
                self._console.print(
                    f"[bold yellow]Resuming from checkpoint:[/bold yellow] "
                    f"{start_idx} rows already processed"
                )
                return results, start_idx
            except Exception as e:
                self._console.print(
                    f"[bold red]Error loading checkpoint:[/bold red] "
                    f"{str(e)}"
                )
                self._console.print("Starting from scratch...")
                return [], 0
        return [], 0

    def _save_checkpoint(self, results: list[dict], checkpoint_path: Path):
        """Save intermediate results to checkpoint file."""
        try:
            checkpoint_df = pl.DataFrame(results)
            checkpoint_df.write_parquet(checkpoint_path)
        except Exception as e:
            self._console.print(
                f"[bold red]Error saving checkpoint:[/bold red] {str(e)}"
            )

    async def _evaluate_row_async(
        self,
        row: dict,
        evaluators: list[BaseEvaluator],
        progress: Progress,
    ) -> dict[str, Union[str, float, None]]:
        """Evaluate a single row with all evaluators in parallel."""
        row_dict: dict[str, Union[str, float, None]] = dict(row)

        eval_task = progress.add_task(
            "[green]Evaluating...", total=len(evaluators)
        )

        # Create a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def bounded_eval(evaluator: BaseEvaluator):
            async with semaphore:
                return await self._evaluate_single_async(
                    evaluator, row, eval_task, progress
                )

        # Create tasks for all evaluators with concurrency control
        tasks = [bounded_eval(evaluator) for evaluator in evaluators]

        # Run all evaluations concurrently (but limited by semaphore)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for evaluator, result in zip(evaluators, results):
            if isinstance(result, Exception):
                self._console.print(
                    f"[bold red]Error in {evaluator.name()}:[/bold red] "
                    f"{str(result)}"
                )
                row_dict[f"{evaluator.name()}_score"] = None
                row_dict[f"{evaluator.name()}_reason"] = None
            elif result is None:
                row_dict[f"{evaluator.name()}_score"] = None
                row_dict[f"{evaluator.name()}_reason"] = None
            else:
                row_dict[f"{evaluator.name()}_score"] = result.score
                row_dict[f"{evaluator.name()}_reason"] = result.reason

        progress.remove_task(eval_task)
        return row_dict

    async def _evaluate_single_async(
        self,
        evaluator: BaseEvaluator,
        row: dict,
        task_id: TaskID,
        progress: Progress,
    ) -> Optional[Result]:
        """Async wrapper for single evaluation."""
        question = row["question"]
        author = row["author"]

        source = Book(
            title=question,
            author=author,
            text=row["expected_answer"],
            language="English",
        )
        target = AnonymousText(text=row["actual_answer"])

        result = None
        for idx in range(self._config.max_retries):
            try:
                # Run the evaluator in a thread pool to avoid blocking
                result = await asyncio.to_thread(
                    evaluator.evaluate,
                    source,
                    target,
                    model_name=self._config.evaluation_gpt_model,
                )
                break
            except Exception as e:
                self._console.print(
                    f"[bold red]Error in {evaluator.name()} "
                    f"(attempt {idx + 1}):[/bold red] {str(e)}"
                )
                if idx == self._config.max_retries - 1:
                    # Last attempt failed
                    break
                await asyncio.sleep(1)  # Brief delay before retry

        progress.update(task_id, advance=1)
        return result