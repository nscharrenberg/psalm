from deepeval.scorer import Scorer
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from psalm.core.models import Book, AnonymousText, Result
from psalm.evaluators.base_evaluator import BaseEvaluator

import nltk
nltk.download('punkt_tab')


class BleuMetric(BaseMetric):
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.scorer = Scorer()

    def measure(self, test_case: LLMTestCase, *args, **kwargs):
        self.score = self.scorer.sentence_bleu_score(
            prediction=test_case.actual_output,
            references=[test_case.expected_output],
            bleu_type="bleu1"
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
        return "BLEU Metric"

class BleuEvaluator(BaseEvaluator):
    @classmethod
    def name(cls) -> str:
        return "BLEU"

    @classmethod
    def description(cls) -> str:
        return """
        Calculates the BLEU (Bilingual Evaluation Understudy) score for a given prediction compared to one or more reference sentences.
        BLEU is a metric used to evaluate the quality of machine-generated text by comparing it to one or more reference sentences.
        It measures the similarity of the generated text to the reference text based on n-grams.
        """

    def evaluate(self, source: Book, target: AnonymousText, **kwargs) -> Result:
        metric = BleuMetric()
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
        metric = BleuMetric()
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