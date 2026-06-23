from __future__ import annotations

import asyncio
from typing import Any

from psalm.agents.defense import Defense
from psalm.agents.judge import Judge
from psalm.agents.juror import Juror
from psalm.agents.prosecutor import Prosecutor
from psalm.courtroom.default import DefaultCourtroom
from psalm.exceptions import PSALMConfigError, PSALMValidationError
from psalm.models.config import AgentConfig, CaseInput, DebateConfig
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

    def with_dimensions(self, dimensions: list[str]) -> PSALM:
        self._debate_config = self._debate_config.model_copy(update={"dimensions": dimensions})
        return self

    def with_debate(self, rounds: int = 5, time_limit_seconds: int = 180) -> PSALM:
        self._debate_config = self._debate_config.model_copy(
            update={"rounds": rounds, "time_limit_seconds": time_limit_seconds}
        )
        return self

    def with_voting(self, strategies: list[str]) -> PSALM:
        self._debate_config = self._debate_config.model_copy(
            update={"voting_strategies": strategies}
        )
        return self

    async def build(self) -> _BuiltPSALM:
        self._validate_config()
        await self._ping_all_llms()
        return self._assemble()

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

    async def _ping_llm(self, config: AgentConfig, role: str) -> None:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            organization=config.org_id,
            model=config.model,
            max_tokens=1,
        )
        try:
            await llm.ainvoke([{"role": "user", "content": "ping"}])
        except Exception as exc:
            raise PSALMConfigError(
                code="PSALM-C006",
                message=f"LLM connection failed for agent '{role}'.",
                context={"role": role, "base_url": config.base_url, "model": config.model},
                suggestion="Check api_key, base_url, and network connectivity.",
                cause=exc,
            ) from exc

    async def _ping_all_llms(self) -> None:
        configs = [
            (self._prosecutor_config, "prosecutor"),
            (self._defense_config, "defense"),
            (self._judge_config, "judge"),
        ] + [(c, f"juror-{i}") for i, c in enumerate(self._jury_configs)]
        await asyncio.gather(*[self._ping_llm(cfg, role) for cfg, role in configs])

    def _assemble(self) -> _BuiltPSALM:
        prosecutor = Prosecutor(config=self._prosecutor_config)
        defense = Defense(config=self._defense_config)
        judge = Judge(config=self._judge_config)
        jury = [Juror(juror_id=f"juror-{i}", config=c) for i, c in enumerate(self._jury_configs)]
        voting_strategies = [
            _STRATEGY_MAP[name]() for name in self._debate_config.voting_strategies
        ]
        arg_phase = ArgumentationPhase(prosecutor, defense, judge, self._debate_config)
        delib_phase = DeliberationPhase(jury, voting_strategies, judge, self._debate_config)
        courtroom = DefaultCourtroom(arg_phase, delib_phase)
        return _BuiltPSALM(courtroom=courtroom, debate_config=self._debate_config)


class _BuiltPSALM:
    def __init__(self, courtroom: DefaultCourtroom, debate_config: DebateConfig) -> None:
        self._courtroom = courtroom
        self._debate_config = debate_config

    def evaluate(self, source_text: str, target_text: str) -> PSALMResult:
        self._validate_inputs(source_text, target_text)
        if source_text.strip() == target_text.strip():
            return self._identical_texts_result(source_text)
        return asyncio.run(self.aevaluate(source_text, target_text))

    async def aevaluate(self, source_text: str, target_text: str) -> PSALMResult:
        self._validate_inputs(source_text, target_text)
        if source_text.strip() == target_text.strip():
            return self._identical_texts_result(source_text)
        case_input = CaseInput(
            source_text=source_text,
            target_text=target_text,
            dimensions=self._debate_config.dimensions,
        )
        return await self._courtroom.run(case_input)

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
        from psalm.models.result import ArgumentationLog, DebateLog, ResultMetadata
        return PSALMResult(
            verdict="Guilty",
            rationale=(
                "Source and target texts are identical — infringement confirmed without agent "
                "evaluation."
            ),
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="none"),
            metadata=ResultMetadata(
                duration_seconds=0.0,
                argumentation_rounds_used=0,
                deliberation_rounds_used=0,
                voting_strategy_applied="none",
            ),
        )
