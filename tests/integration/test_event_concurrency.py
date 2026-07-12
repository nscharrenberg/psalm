from unittest.mock import AsyncMock, patch

from psalm import PSALM
from psalm.dimensions import CHARACTER, PLOT
from psalm.events.types import ArgumentSubmitted, DimensionStarted, DimensionVerdictReached
from psalm.models.evidence import Argument, ArgumentBatch, Proof
from psalm.models.result import JurorVote, ValidationResult


def _agent_kwargs():
    return {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o"}


def _jury_configs():
    return [
        {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o", "seed": i}
        for i in range(3)
    ]


def _make_arg_side_effect(role: str):
    async def _side_effect(*, dimensions, **kwargs):
        dim_name = dimensions[0].name
        proof = Proof(source_excerpt="x", target_excerpt="y", relevance="r")
        arg = Argument(
            claim=f"{dim_name}-claim", dimension=dim_name, proofs=[proof],
            agent_role=role, round=kwargs["round"],
        )
        return ArgumentBatch(arguments=[arg])
    return _side_effect


async def test_concurrent_dimensions_events_correctly_tagged():
    no_further = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")

    with (
        patch("psalm.agents.prosecutor.Prosecutor.gather_arguments",
              new=AsyncMock(side_effect=_make_arg_side_effect("prosecutor"))),
        patch("psalm.agents.prosecutor.Prosecutor.gather_counter_arguments", new=AsyncMock(return_value=no_further)),
        patch("psalm.agents.defense.Defense.gather_counter_arguments",
              new=AsyncMock(side_effect=_make_arg_side_effect("defense"))),
        patch("psalm.agents.defense.Defense.gather_arguments", new=AsyncMock(return_value=no_further)),
        patch("psalm.agents.prosecutor.Prosecutor.deliver_closing_argument", new=AsyncMock(return_value="P closing.")),
        patch("psalm.agents.defense.Defense.deliver_closing_argument", new=AsyncMock(return_value="D closing.")),
        patch("psalm.agents.judge.Judge.validate_argument", new=AsyncMock(return_value=ValidationResult(is_valid=True))),
        patch("psalm.agents.judge.Judge.detect_stability", new=AsyncMock(return_value=False)),
        patch("psalm.agents.judge.Judge.validate_batch_completeness", new=AsyncMock(return_value=True)),
        patch("psalm.agents.juror.Juror.discuss", new=AsyncMock(return_value="Discussing.")),
        patch("psalm.agents.juror.Juror.vote", new=AsyncMock(
            return_value=JurorVote(juror_id="juror-0", vote="Guilty", rationale="r"))),
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
    ):
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .with_dimensions([CHARACTER, PLOT])
            .with_debate(argumentation_rounds=1, deliberation_rounds=1, time_limit_seconds=60)
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .build()
        )
        events = [
            e async for e in psalm.astream_evaluate(
                "source text about wizards", "target text about wizards, longer",
            )
        ]

    sequences = [e.sequence for e in events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))

    submitted = [e for e in events if isinstance(e, ArgumentSubmitted)]
    assert len(submitted) > 0
    for e in submitted:
        assert e.dimension == e.argument.dimension

    started = {e.dimension for e in events if isinstance(e, DimensionStarted)}
    reached = {e.dimension for e in events if isinstance(e, DimensionVerdictReached)}
    assert started == {CHARACTER.name, PLOT.name}
    assert reached == {CHARACTER.name, PLOT.name}
