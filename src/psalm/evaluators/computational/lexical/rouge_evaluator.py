from deepeval.scorer import Scorer
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from psalm.core.models import Book, AnonymousText, Result
from psalm.evaluators.base_evaluator import BaseEvaluator

import nltk
nltk.download('punkt_tab')

class RougeMetric(BaseMetric):
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.scorer = Scorer()

    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        self.score = self.scorer.rouge_score(
            prediction=test_case.actual_output,
            target=test_case.expected_output,
            score_type="rouge1"
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
        return "Rouge Metric"

class RougeEvaluator(BaseEvaluator):
    @classmethod
    def name(cls) -> str:
        return "ROUGE"

    @classmethod
    def description(cls) -> str:
        return """
        Calculates the Rouge score for a given target and prediction.
        Rouge (Recall-Oriented Understudy for Gisting Evaluation) is a metric used for evaluating the quality of generated text,
        especially in tasks like text summarization.
        """

    def evaluate(self, source: Book, target: AnonymousText, **kwargs) -> Result:
        metric = RougeMetric()
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
        metric = RougeMetric()
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