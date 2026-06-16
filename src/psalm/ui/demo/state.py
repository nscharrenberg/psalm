from dataclasses import dataclass, field
from typing import Any


@dataclass
class CopyrightText:
    title: str = ""
    author: str = ""
    text: str = ""

    def __hash__(self):
        return hash((self.title, self.author, self.text))


@dataclass
class TargetText:
    title: str = ""
    author: str = ""
    text: str = ""

    def __hash__(self):
        return hash((self.title, self.author, self.text))


@dataclass
class LLMParameters:
    model_name: str = "gpt-5-nano"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    temperature: float = 0.1

    def __hash__(self):
        return hash(
            (
                self.model_name,
                self.base_url,
                self.api_key,
                self.temperature,
            )
        )


@dataclass
class EvaluationParameters:
    llm_params: LLMParameters = field(
        default_factory=lambda: LLMParameters()
    )
    max_concurrency: int = 1
    wait_time: float = 0.5
    timeout: float = 300.0
    debug: bool = False

    def __hash__(self):
        return hash(
            (
                self.llm_params,
                self.max_concurrency,
                self.wait_time,
                self.timeout,
                self.debug,
            )
        )


@dataclass
class DemoState:
    current_step: int = 0
    copyright_text: CopyrightText = field(
        default_factory=lambda: CopyrightText()
    )
    target_text: TargetText = field(default_factory=lambda: TargetText())
    evaluators: list[str] = field(default_factory=list)
    evaluation_params: EvaluationParameters = field(
        default_factory=lambda: EvaluationParameters()
    )
    results: list[dict[str, Any]] = field(default_factory=list)
    is_analysis_running: bool = False
    analysis_complete: bool = False
    console_log: str = ""

    def reset_analysis(self) -> None:
        self.results = []
        self.is_analysis_running = False
        self.analysis_complete = False
        self.console_log = ""

    def append_log(self, message: str) -> None:
        if not message.endswith("\n"):
            message += "\n"
        self.console_log += message

    def __hash__(self):
        def make_hashable(obj):
            if isinstance(obj, dict):
                return tuple(
                    (k, make_hashable(v)) for k, v in sorted(obj.items())
                )
            if isinstance(obj, (list, tuple)):
                return tuple(make_hashable(item) for item in obj)
            return obj

        hashable_results = tuple(
            make_hashable(result) for result in self.results
        )

        return hash(
            (
                self.current_step,
                self.copyright_text,
                self.target_text,
                tuple(self.evaluators),
                self.evaluation_params,
                hashable_results,
                self.is_analysis_running,
                self.analysis_complete,
                self.console_log,
            )
        )