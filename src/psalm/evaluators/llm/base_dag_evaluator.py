from abc import abstractmethod, ABC
from typing import Union

from deepeval.metrics import DAGMetric, GEval
from deepeval.test_case import LLMTestCase

from psalm.core.models import Book, AnonymousText, Result
from psalm.evaluators.base_evaluator import BaseEvaluator


class BaseDagEvaluator(BaseEvaluator, ABC):
    def evaluate(self, source: Book, target: AnonymousText, **kwargs) -> Result:
        test_case, metric = self.get_test_case(source, target, **kwargs)

        metric.measure(test_case)

        return self.get_report(metric, source, target, **kwargs)

    def evaluate_with_metric(self, source: Book, target: AnonymousText, **kwargs) -> tuple[Result, DAGMetric]:
        test_case, metric = self.get_test_case(source, target, **kwargs)

        metric.measure(test_case)

        return self.get_report(metric, source, target, **kwargs), metric

    async def a_evaluate(
            self, source: Book, target: AnonymousText, **kwargs
    ) -> Result:
        test_case, metric = self.get_test_case(source, target, **kwargs)

        await metric.a_measure(test_case)

        return self.get_report(metric, source, target, **kwargs)

    @abstractmethod
    def _build_evaluation_dag(
            self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        pass

    def get_test_case(
        self, source: Book, target: AnonymousText, **kwargs
    ) -> tuple[LLMTestCase, Union[DAGMetric, GEval]]:
        model_name: str = self.get_model_name(**kwargs)
        threshold: float = self.get_threshold(**kwargs)
        debug: bool = self.debug(**kwargs)
        metric = self._build_evaluation_dag(model_name=model_name, threshold=threshold, verbose_mode=debug)

        question = self.get_question(**kwargs)

        return (
            LLMTestCase(input=question, actual_output=target.text, expected_output=source.text),
            metric,
        )

    def get_report(
        self, metric: Union[GEval, DAGMetric], source: Book, target: AnonymousText, **kwargs
    ) -> Result:
        score = metric.score if metric.score is not None else -1
        reason = metric.reason if metric.reason is not None else None

        details = kwargs

        if metric.verbose_logs is not None and len(metric.verbose_logs) > 0:
            details["verbose_logs"] = metric.verbose_logs

        # # Fix DeepEval bug regarding score and reasoning score mismatch.
        # # Assume Reasoning Score is correct score.
        # if reason is not None:
        #     # Extract the score from the reason if it contains one
        #     # Reason format: "The score is 0.5 because ..."
        #     if " because " in reason:
        #         score_part = reason.split(" because ")[0]
        #         try:
        #             initial_score = score
        #             # Extract numeric score from "The score is X"
        #             extracted_score = float(score_part.replace("The score is", "").strip())
        #             score = extracted_score
        #             details["initial_score"] = str(initial_score)
        #         except (ValueError, AttributeError):
        #             # If extraction fails, keep the original metric.score
        #             pass
        #
        #         # Clean up the reason to only include the explanation
        #         # reason = reason.split(" because ", 1)[1]

        return Result(
            source=source,
            target=target,
            evaluator=self.name(),
            score=score,
            reason=reason,
            details=details,
            confidence=self.compute_confidence(score),
        )

    def get_model_name(self, **kwargs) -> str:
        model_name = "gpt-4o-mini"

        if "model_name" in kwargs and kwargs["model_name"] is not None:
            model_name = str(kwargs["model_name"]).strip()

        return model_name

    def get_threshold(self, **kwargs) -> float:
        threshold = 0.0

        if "threshold" in kwargs and kwargs["threshold"] is not None:
            threshold = float(kwargs["threshold"])

        return threshold

    def debug(self, **kwargs):
        debug = False

        if "debug" in kwargs and kwargs["debug"] is not None:
            if type(kwargs["debug"]) is bool:
                debug = bool(kwargs["debug"])
            else:
                debug = bool(str(kwargs["debug"]).lower() in ["true", "yes", "1", "on"])

        return debug

    def get_question(self, **kwargs):
        """Generate or retrieve the evaluation question/task description."""
        if "question" in kwargs and kwargs["question"] is not None:
            return str(kwargs["question"])

        return ""