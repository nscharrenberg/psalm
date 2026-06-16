import json
from pathlib import Path
from typing import TypeVar
import asyncio

from rich.console import Console
from rich.progress import track, Progress
from rich.status import Status

from psalm.configs.experiments import ControlExperimentConfig
from psalm.core.models import Book, AnonymousText, Result
from psalm.evaluators.base_evaluator import BaseEvaluator
from sdg.validations import ControlDataset

_BE = TypeVar("_BE", bound=BaseEvaluator)
_EvaluatorClass = type[_BE]


class ControlExperiment:
    def __init__(self, config: ControlExperimentConfig, evaluator_type: _EvaluatorClass):
        self._config = config
        self._console = Console()
        self._evaluator_type = evaluator_type

    def execute(self, use_async: bool = False) -> tuple[dict[str, Result], dict[str, list[str]]]:
        """Execute the control experiment.

        Args:
            use_async: If True, use async execution for parallel evaluation.
        """
        if use_async:
            return asyncio.run(self._execute_async())
        else:
            return self._execute_sync()

    def _execute_sync(self) -> tuple[dict[str, Result], dict[str, list[str]]]:
        """Original synchronous execution."""
        self._console.rule("Control Experiment")
        dataset = self.load_data()
        results, errors = self.batch_evaluate(dataset=dataset)

        try:
            self.save(results=results, errors=errors, dataset=dataset)
        except Exception as e:
            self._console.print(f"[red]Failed to save Control Results: {str(e)}[/red]")

        self._console.rule("Control Experiment Complete")

        return results, errors

    async def _execute_async(self) -> tuple[dict[str, Result], dict[str, list[str]]]:
        """Async execution with parallel evaluation."""
        self._console.rule("Control Experiment (Async)")
        dataset = self.load_data()
        results, errors = await self.batch_evaluate_async(dataset=dataset)

        try:
            self.save(results=results, errors=errors, dataset=dataset)
        except Exception as e:
            self._console.print(f"[red]Failed to save Control Results: {str(e)}[/red]")

        self._console.rule("Control Experiment Complete")

        return results, errors

    def load_data(self) -> ControlDataset:
        with Status("Loading Control Dataset", spinner="clock") as status:
            dataset_path = Path(self._config.dataset_path)

            if not dataset_path.suffix == ".json":
                raise ValueError("Control Dataset path must be a JSON file.")

            if not dataset_path.exists():
                raise ValueError(f"Control Dataset path \"{dataset_path}\" does not exist.")

            with open(dataset_path) as json_file:
                data = json.load(json_file)

            status.update("Validating Control Dataset", spinner="earth")

            return ControlDataset.model_validate(data)

    def evaluate(self, source_text: Book, target_text: AnonymousText) -> Result:
        evaluator = self._evaluator_type()

        return evaluator.evaluate(source_text, target_text, model_name=self._config.model.model_name,
                                  debug=self._config.debug)

    def batch_evaluate(self, dataset: ControlDataset) -> tuple[dict[str, Result], dict[str, list[str]]]:
        """Synchronous batch evaluation."""
        evaluator_name = self._evaluator_type().name()

        with Status("Evaluating Control Dataset", spinner="monkey") as status:
            results = {}
            error_log = {}

            source = dataset.source
            variants = dataset.variants

            for variant in track(variants, total=len(variants), description="Evaluating variants",
                                 console=self._console, transient=True):
                self._console.rule(f"OUTPUT for expected score \"{variant.expected_score}\"")
                target_text = variant.text
                expected_score = variant.expected_score
                variant_name = variant.text_similarity
                max_retries = self._config.max_retries

                status.update(f"Evaluating Control Dataset (\"{variant_name}\")", spinner="monkey")
                result = None
                errors = []

                # Calls may fail due to network issues, so we retry a few times
                for i in range(max_retries):
                    try:
                        result = self.evaluate(source, target_text)
                        break
                    except Exception as e:
                        status.update(f"Evaluating Control Dataset (\"{variant_name}\" Retrying {i + 1}/{max_retries})",
                                      spinner="monkey")
                        errors.append(str(e))
                        continue

                if result is None:
                    # Only need to log when failed to evaluate
                    error_log[variant_name] = errors

                    # Set default result to failed to evaluate
                    results[variant_name] = Result(source=source, target=target_text, score=-1,
                                                   reason="Failed to evaluate", confidence=0.0,
                                                   evaluator=evaluator_name, details={"errors": errors})
                    continue

                status.update(
                    f"Evaluating Control Dataset (\"{variant_name}\", score: {result.score}, expected: {expected_score})",
                    spinner="smiley")
                results[variant_name] = result

            return results, error_log

    async def batch_evaluate_async(self, dataset: ControlDataset) -> tuple[dict[str, Result], dict[str, list[str]]]:
        """Async batch evaluation with parallel processing."""
        evaluator_name = self._evaluator_type().name()
        source = dataset.source
        variants = dataset.variants

        # Get max_concurrent from config, default to 5 if not set
        max_concurrent = getattr(self._config, 'max_concurrent', 5)

        results = {}
        error_log = {}

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Evaluating variants...", total=len(variants)
            )

            # Create a semaphore to limit concurrency
            semaphore = asyncio.Semaphore(max_concurrent)

            async def evaluate_variant_bounded(variant):
                async with semaphore:
                    return await self._evaluate_variant_async(
                        variant, source, evaluator_name
                    )

            # Create tasks for all variants
            tasks = [evaluate_variant_bounded(variant) for variant in variants]

            # Run all evaluations concurrently (but limited by semaphore)
            variant_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for variant, result_data in zip(variants, variant_results):
                variant_name = variant.text_similarity
                expected_score = variant.expected_score

                if isinstance(result_data, Exception):
                    self._console.print(
                        f"[bold red]Error evaluating {variant_name}:[/bold red] "
                        f"{str(result_data)}"
                    )
                    error_log[variant_name] = [str(result_data)]
                    results[variant_name] = Result(
                        source=source,
                        target=variant.text,
                        score=-1,
                        reason="Failed to evaluate",
                        confidence=0.0,
                        evaluator=evaluator_name,
                        details={"errors": [str(result_data)]}
                    )
                else:
                    result, errors = result_data
                    if result is None:
                        error_log[variant_name] = errors
                        results[variant_name] = Result(
                            source=source,
                            target=variant.text,
                            score=-1,
                            reason="Failed to evaluate",
                            confidence=0.0,
                            evaluator=evaluator_name,
                            details={"errors": errors}
                        )
                    else:
                        self._console.rule(
                            f"OUTPUT for expected score \"{expected_score}\""
                        )
                        self._console.print(
                            f"[green]{variant_name}: score={result.score}, "
                            f"expected={expected_score}[/green]"
                        )
                        results[variant_name] = result

                progress.update(task, advance=1)

        return results, error_log

    async def _evaluate_variant_async(
            self,
            variant,
            source: Book,
            evaluator_name: str
    ) -> tuple[Result | None, list[str]]:
        """Async evaluation of a single variant with retry logic."""
        target_text = variant.text
        variant_name = variant.text_similarity
        max_retries = self._config.max_retries

        result = None
        errors = []

        for i in range(max_retries):
            try:
                # Run the evaluator in a thread pool to avoid blocking
                result = await asyncio.to_thread(
                    self.evaluate,
                    source,
                    target_text
                )
                break
            except Exception as e:
                error_msg = f"Attempt {i + 1}/{max_retries}: {str(e)}"
                errors.append(error_msg)
                if i < max_retries - 1:
                    # Brief delay before retry (exponential backoff)
                    await asyncio.sleep(2 ** i)

        return result, errors

    def save(self, results: dict[str, Result], errors: dict[str, list[str]], dataset: ControlDataset) -> str:
        with Status("Saving Control Results", spinner="moon") as status:
            control_name = dataset.control_case

            save_dir = self._config.save_dir

            if save_dir is None:
                save_dir = Path(self._config.dataset_path).parent / "control_results"

            save_dir.mkdir(exist_ok=True)

            save_path = save_dir / f"{control_name}.json"

            formatted_results = {}

            for variant_name, result in results.items():
                formatted_results[variant_name] = result.model_dump()

                # Add expected_score to the result
                for variant_item in dataset.variants:
                    if variant_item.text_similarity == variant_name:
                        formatted_results[variant_name]["expected_score"] = variant_item.expected_score
                        break

            with open(save_path, "w") as f:
                json.dump(formatted_results, f, indent=4, default=str)

            if errors:
                status.update("Saving Control Errors", spinner="grenade")
                error_path = save_dir / f"{control_name}_errors.json"

                with open(error_path, "w") as f:
                    json.dump(errors, f, indent=4)

        return str(save_dir)