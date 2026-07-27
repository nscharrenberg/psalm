from __future__ import annotations

import asyncio
import inspect
import random
from typing import Any, AsyncIterator, Callable
from uuid import uuid4

from pydantic import SecretStr

from psalm.agents.base import _RunExecution
from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.juror import Juror
from psalm.agents.prosecutor import Prosecutor
from psalm.courtroom.default import DefaultCourtroom
from psalm.dimensions.base import Dimension
from psalm.events import EventSink, FinalVerdictReached, PSALMEvent, RunFailed, RunStarted, emit
from psalm.events.context import _current_sink
from psalm.exceptions import PSALMConfigError, PSALMValidationError
from psalm.models.config import (
    AgentConfig,
    CaseInput,
    DebateConfig,
    EvaluationStrategy,
    ExecutionConfig,
)
from psalm.models.result import PSALMResult
from psalm.phases.argumentation import ArgumentationPhase
from psalm.phases.deliberation import DeliberationPhase
from psalm.voting.judge_tiebreaker import JudgeTiebreakerVoting
from psalm.voting.simple_majority import SimpleMajorityVoting
from psalm.voting.trust_weighted import TrustWeightedVoting

_STRATEGY_MAP = {
    "simple_majority": SimpleMajorityVoting,
    "trust_weighted": TrustWeightedVoting,
    "judge_tiebreaker": JudgeTiebreakerVoting,
}


class PSALM:
    def __init__(self) -> None:
        self._prosecutor_config: AgentConfig | None = None
        self._defense_config: AgentConfig | None = None
        self._judge_config: AgentConfig | None = None
        self._jury_configs: list[AgentConfig] = []
        self._debate_config = DebateConfig()
        self._execution_config: ExecutionConfig = ExecutionConfig()
        self._event_listeners: list[Callable[[PSALMEvent], Any]] = []

    def with_prosecutor(self, base_url: str, api_key: str, model: str, **kwargs: Any) -> PSALM:
        self._prosecutor_config = AgentConfig(
            base_url=base_url, api_key=api_key, model=model, **kwargs
        )
        return self

    def with_defense(self, base_url: str, api_key: str, model: str, **kwargs: Any) -> PSALM:
        self._defense_config = AgentConfig(
            base_url=base_url, api_key=api_key, model=model, **kwargs
        )
        return self

    def with_judge(self, base_url: str, api_key: str, model: str, **kwargs: Any) -> PSALM:
        self._judge_config = AgentConfig(base_url=base_url, api_key=api_key, model=model, **kwargs)
        return self

    def with_jury(self, configs: list[dict[str, Any] | AgentConfig]) -> PSALM:
        self._jury_configs = [
            c if isinstance(c, AgentConfig) else AgentConfig(**c)
            for c in configs
        ]
        return self

    def with_dimensions(self, dimensions: list[Dimension]) -> PSALM:
        self._debate_config = self._debate_config.model_copy(update={"dimensions": dimensions})
        return self

    def with_debate(
        self,
        argumentation_rounds: int = 3,
        deliberation_rounds: int = 2,
        time_limit_seconds: int = 180,
    ) -> PSALM:
        self._debate_config = self._debate_config.model_copy(
            update={
                "argumentation_rounds": argumentation_rounds,
                "deliberation_rounds": deliberation_rounds,
                "time_limit_seconds": time_limit_seconds,
            }
        )
        return self

    def with_voting(self, strategies: list[str]) -> PSALM:
        self._debate_config = self._debate_config.model_copy(
            update={"voting_strategies": strategies}
        )
        return self

    def with_evaluation_strategy(self, strategy: EvaluationStrategy) -> PSALM:
        self._debate_config = self._debate_config.model_copy(
            update={"evaluation_strategy": strategy}
        )
        return self

    def with_execution(
        self,
        max_concurrent_llm_calls: int = 8,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        max_requests_per_minute: int | None = 60,
        max_tokens_per_minute: int | None = 40000,
        retry_after_fallback_seconds: float | None = None,
    ) -> PSALM:
        self._execution_config = ExecutionConfig(
            max_concurrent_llm_calls=max_concurrent_llm_calls,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            max_requests_per_minute=max_requests_per_minute,
            max_tokens_per_minute=max_tokens_per_minute,
            retry_after_fallback_seconds=retry_after_fallback_seconds,
        )
        return self

    def with_event_listener(self, listener: Callable[[PSALMEvent], Any]) -> PSALM:
        self._event_listeners.append(listener)
        return self

    async def build(self) -> _BuiltPSALM:
        self._validate_config()
        execution = _RunExecution(
            max_concurrent_llm_calls=self._execution_config.max_concurrent_llm_calls,
            max_retries=self._execution_config.max_retries,
            backoff_factor=self._execution_config.backoff_factor,
            max_requests_per_minute=self._execution_config.max_requests_per_minute,
            max_tokens_per_minute=self._execution_config.max_tokens_per_minute,
            retry_after_fallback_seconds=self._execution_config.retry_after_fallback_seconds,
        )
        await self._ping_all_llms(execution)
        return self._assemble(execution)

    def _validate_config(self) -> None:
        if self._prosecutor_config is None:
            raise PSALMConfigError(
                code="PSALM-C001",
                message="Missing required agent: prosecutor.",
                context={"missing": "prosecutor"},
                suggestion=(
                    "Call .with_prosecutor(base_url=..., api_key=..., model=...) on the builder."
                ),
            )
        if self._defense_config is None:
            raise PSALMConfigError(
                code="PSALM-C001",
                message="Missing required agent: defense.",
                context={"missing": "defense"},
                suggestion=(
                    "Call .with_defense(base_url=..., api_key=..., model=...) on the builder."
                ),
            )
        if self._judge_config is None:
            raise PSALMConfigError(
                code="PSALM-C001",
                message="Missing required agent: judge.",
                context={"missing": "judge"},
                suggestion="Call .with_judge(base_url=..., api_key=..., model=...) on the builder.",
            )
        if len(self._jury_configs) < 3:
            raise PSALMConfigError(
                code="PSALM-C002",
                message=f"Jury requires a minimum of 3 members, got {len(self._jury_configs)}.",
                context={"jury_size": len(self._jury_configs), "minimum_required": 3},
                suggestion="Add at least one more AgentConfig to .with_jury([...]).",
            )

    async def _ping_llm(self, config: AgentConfig, role: str, execution: _RunExecution) -> None:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=SecretStr(config.api_key) if config.api_key else None,
            organization=config.org_id,
            model=config.model,
            max_completion_tokens=1,
        )
        last_exc: Exception | None = None
        for attempt in range(execution.max_retries):
            try:
                async with execution.semaphore():
                    await llm.ainvoke([{"role": "user", "content": "ping"}])
                return
            except Exception as exc:
                last_exc = exc
                if attempt < execution.max_retries - 1:
                    backoff = execution.backoff_factor**attempt
                    await asyncio.sleep(random.uniform(0, backoff))
        raise PSALMConfigError(
            code="PSALM-C006",
            message=f"LLM connection failed for agent '{role}'.",
            context={"role": role, "base_url": config.base_url, "model": config.model},
            suggestion="Check api_key, base_url, and network connectivity.",
            cause=last_exc,
        ) from last_exc

    async def _ping_all_llms(self, execution: _RunExecution) -> None:
        assert self._prosecutor_config is not None
        assert self._defense_config is not None
        assert self._judge_config is not None
        configs = [
            (self._prosecutor_config, "prosecutor"),
            (self._defense_config, "defense"),
            (self._judge_config, "judge"),
        ] + [(c, f"juror-{i}") for i, c in enumerate(self._jury_configs)]
        await asyncio.gather(*[self._ping_llm(cfg, role, execution) for cfg, role in configs])

    def _assemble(self, execution: _RunExecution) -> _BuiltPSALM:
        assert self._prosecutor_config is not None
        assert self._defense_config is not None
        assert self._judge_config is not None
        prosecutor = Prosecutor(config=self._prosecutor_config, execution=execution)
        defense = Defense(config=self._defense_config, execution=execution)
        judge = Judge(config=self._judge_config, execution=execution)
        jury = [
            Juror(juror_id=f"juror-{i}", config=c, execution=execution)
            for i, c in enumerate(self._jury_configs)
        ]
        voting_strategies = [
            _STRATEGY_MAP[name]() for name in self._debate_config.voting_strategies
        ]
        arg_phase = ArgumentationPhase(prosecutor, defense, judge, self._debate_config)
        strategy = self._debate_config.evaluation_strategy
        if strategy == EvaluationStrategy.SHARED_ALL:
            # One shared deliberation phase for all dimensions
            deliberation_phases = [
                DeliberationPhase(jury, voting_strategies, judge, self._debate_config)
            ]
        else:
            # One DeliberationPhase per dimension (FULLY_SEPARATE and SHARED_ARG)
            deliberation_phases = [
                DeliberationPhase(jury, voting_strategies, judge, self._debate_config)
                for _ in self._debate_config.dimensions
            ]
        courtroom = DefaultCourtroom(arg_phase, deliberation_phases, self._debate_config)
        return _BuiltPSALM(
            courtroom=courtroom,
            debate_config=self._debate_config,
            event_listeners=self._event_listeners,
        )


class _BuiltPSALM:
    def __init__(
        self,
        courtroom: DefaultCourtroom,
        debate_config: DebateConfig,
        event_listeners: list[Callable[[PSALMEvent], Any]] | None = None,
    ) -> None:
        self._courtroom = courtroom
        self._debate_config = debate_config
        self._event_listeners = event_listeners or []

    def evaluate(self, source_text: str, target_text: str) -> PSALMResult:
        if not self._event_listeners:
            self._validate_inputs(source_text, target_text)
            if source_text.strip() == target_text.strip():
                return self._identical_texts_result(source_text)
        return asyncio.run(self.aevaluate(source_text, target_text))

    async def aevaluate(self, source_text: str, target_text: str) -> PSALMResult:
        if not self._event_listeners:
            self._validate_inputs(source_text, target_text)
            if source_text.strip() == target_text.strip():
                return self._identical_texts_result(source_text)
            case_input = CaseInput(
                source_text=source_text,
                target_text=target_text,
                dimensions=self._debate_config.dimensions,
            )
            return await self._courtroom.run(case_input)

        result: PSALMResult | None = None
        async for event in self.astream_evaluate(source_text, target_text):
            for listener in self._event_listeners:
                outcome = listener(event)
                if inspect.isawaitable(outcome):
                    await outcome
            if isinstance(event, FinalVerdictReached):
                result = event.result
        if result is None:
            raise RuntimeError(
                "astream_evaluate() completed without emitting FinalVerdictReached."
            )
        return result

    async def astream_evaluate(
        self, source_text: str, target_text: str
    ) -> AsyncIterator[PSALMEvent]:
        self._validate_inputs(source_text, target_text)
        run_id = str(uuid4())
        sink = EventSink(run_id)

        async def _run() -> PSALMResult:
            _current_sink.set(sink)
            await emit(RunStarted(
                dimensions=[d.name for d in self._debate_config.dimensions],
                evaluation_strategy=self._debate_config.evaluation_strategy.value,
                source_length=len(source_text),
                target_length=len(target_text),
            ))
            if source_text.strip() == target_text.strip():
                return await self._aidentical_texts_result(source_text)
            case_input = CaseInput(
                source_text=source_text,
                target_text=target_text,
                dimensions=self._debate_config.dimensions,
            )
            return await self._courtroom.run(case_input)

        task = asyncio.create_task(_run())
        try:
            while not task.done() or not sink.empty():
                get_task = asyncio.ensure_future(sink.get())
                done, _pending = await asyncio.wait(
                    {task, get_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if get_task in done:
                    yield get_task.result()
                else:
                    get_task.cancel()
            await task
        except Exception as exc:
            code = getattr(exc, "code", "PSALM-UNKNOWN")
            context = getattr(exc, "context", {})
            await sink.put(RunFailed(code=code, message=str(exc), context=context))
            while not sink.empty():
                yield await sink.get()
            raise

    def _validate_inputs(self, source_text: str, target_text: str) -> None:
        if not source_text or not source_text.strip():
            raise PSALMValidationError(
                code="PSALM-V001",
                message="Source text cannot be empty.",
                context={"source_text_length": len(source_text)},
                suggestion="Provide a non-empty source text to .evaluate().",
            )
        if not target_text or not target_text.strip():
            raise PSALMValidationError(
                code="PSALM-V002",
                message="Target text cannot be empty.",
                context={"target_text_length": len(target_text)},
                suggestion="Provide a non-empty target text to .evaluate().",
            )

    def _identical_texts_result(self, text: str) -> PSALMResult:
        from psalm.models.result import (
            ArgumentationLog,
            DebateLog,
            DimensionVerdict,
            ResultMetadata,
        )
        dim_verdicts = [
            DimensionVerdict(
                dimension=dim.name,
                dimension_type=dim.dimension_type,
                importance=dim.importance,
                verdict="Guilty",
                weighted_score=1.0,
                argumentation_log=ArgumentationLog(rounds=[]),
                debate_log=DebateLog(rounds=[], final_voting_strategy_applied="none"),
            )
            for dim in self._debate_config.dimensions
        ]
        return PSALMResult(
            verdict="Guilty",
            rationale=(
                "Source and target texts are identical — infringement confirmed without agent "
                "evaluation."
            ),
            dimension_verdicts=dim_verdicts,
            metadata=ResultMetadata(
                duration_seconds=0.0,
                argumentation_rounds_used=0,
                deliberation_rounds_used=0,
                voting_strategy_applied="none",
            ),
        )

    async def _aidentical_texts_result(self, text: str) -> PSALMResult:
        from psalm.events import DimensionVerdictReached

        result = self._identical_texts_result(text)
        for dv in result.dimension_verdicts:
            await emit(DimensionVerdictReached(
                dimension_type=dv.dimension_type, importance=dv.importance.value,
                verdict=dv.verdict, weighted_score=dv.weighted_score,
            ))
        await emit(FinalVerdictReached(result=result))
        return result
