from deepeval.scorer import Scorer
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from psalm.core.models import Book, AnonymousText, Result
from psalm.evaluators.base_evaluator import BaseEvaluator


class ExactMatchMetric(BaseMetric):
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.scorer = Scorer()

    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        self.score = self.scorer.quasi_exact_match_score(
            prediction=test_case.actual_output,
            target=test_case.expected_output
        )
        self.success = self.score >= self.threshold
        return self.score

    # Async implementation of measure(). If async version for
    # scoring method does not exist, just reuse the measure method.
    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs):
        return self.measure(test_case)

    def is_successful(self):
        return self.success

    @property
    def __name__(self):
        return "Exact Match Metric"

class ExactMatchEvaluator(BaseEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Exact Match"

    @classmethod
    def description(cls) -> str:
        return """
        Calculates the exact match (After normalization) score for a given prediction compared to one a target text.
        """

    def evaluate(self, source: Book, target: AnonymousText, **kwargs) -> Result:
        metric = ExactMatchMetric()
        question = self.get_question(**kwargs)
        test_case = LLMTestCase(input=question, actual_output=target.text, expected_output=source.text)

        metric.measure(test_case)

        details = kwargs

        return Result(
            source=source,
            target=target,
            evaluator=self.name(),
            score=metric.score,
            reason=metric.reason,
            details=details,
            confidence=self.compute_confidence(metric.score),
        )

    async def a_evaluate(self, source: Book, target: AnonymousText, **kwargs) -> Result:
        metric = ExactMatchMetric()
        question = self.get_question(**kwargs)
        test_case = LLMTestCase(input=question, actual_output=target.text, expected_output=source.text)

        await metric.a_measure(test_case)

        details = kwargs

        return Result(
            source=source,
            target=target,
            evaluator=self.name(),
            score=metric.score,
            reason=metric.reason,
            details=details,
            confidence=self.compute_confidence(metric.score),
        )

    def get_question(self, **kwargs):
        """Generate or retrieve the evaluation question/task description."""
        if "question" in kwargs and kwargs["question"] is not None:
            return str(kwargs["question"])

        return ""