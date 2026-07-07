# tests/e2e/test_full_evaluation.py
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from psalm import PSALM, PSALMResult
from psalm.dimensions import CHARACTER, PLOT, WORLD_BUILDING
from psalm.models.result import JurorVote, ValidationResult

CASES_PATH = Path(__file__).parent / "fixtures" / "cases.json"


@pytest.fixture
def cases():
    return json.loads(CASES_PATH.read_text())


def _agent_kwargs():
    return {"base_url": "https://api.openai.com/v1", "api_key": "sk-test", "model": "gpt-4o"}


def _jury_configs():
    return [
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model": "gpt-4o",
            "seed": i,
        }
        for i in range(3)
    ]


@pytest.mark.skipif(
    os.getenv("PSALM_E2E") != "true",
    reason="Set PSALM_E2E=true to run real LLM tests",
)
async def test_e2e_real_llm(cases):
    psalm = await (
        PSALM()
        .with_prosecutor(**_agent_kwargs())
        .with_defense(**_agent_kwargs())
        .with_judge(**_agent_kwargs())
        .with_jury(_jury_configs())
        .with_dimensions([CHARACTER, PLOT, WORLD_BUILDING])
        .with_debate(argumentation_rounds=2, deliberation_rounds=2, time_limit_seconds=120)
        .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
        .build()
    )
    for case in cases:
        result = await psalm.aevaluate(source_text=case["source"], target_text=case["target"])
        assert isinstance(result, PSALMResult)
        assert result.verdict in {"Guilty", "Not Guilty", "Undecided"}


async def test_e2e_mock_full_pipeline(cases):
    from psalm.models.evidence import Argument, ArgumentBatch, Proof

    sample_proof = Proof(
        source_excerpt="silver hair that shimmered like moonlight",
        target_excerpt="shimmering silver locks",
        relevance="Both describe the same distinctive silver hair.",
    )
    sample_arg = Argument(
        claim="Characters share silver hair trait.",
        dimension="character",
        proofs=[sample_proof],
        agent_role="prosecutor",
        round=1,
    )
    sample_counter = Argument(
        claim="Silver hair is a generic fantasy trope.",
        dimension="character",
        proofs=[sample_proof],
        agent_role="defense",
        round=1,
    )
    no_further = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further to add.")

    with (
        patch(
            "psalm.agents.prosecutor.Prosecutor.gather_arguments",
            new=AsyncMock(return_value=ArgumentBatch(arguments=[sample_arg])),
        ),
        patch(
            "psalm.agents.prosecutor.Prosecutor.gather_counter_arguments",
            new=AsyncMock(return_value=no_further),
        ),
        patch(
            "psalm.agents.defense.Defense.gather_counter_arguments",
            new=AsyncMock(return_value=ArgumentBatch(arguments=[sample_counter])),
        ),
        patch(
            "psalm.agents.defense.Defense.gather_arguments",
            new=AsyncMock(return_value=no_further),
        ),
        patch(
            "psalm.agents.judge.Judge.validate_argument",
            new=AsyncMock(return_value=ValidationResult(is_valid=True)),
        ),
        patch(
            "psalm.agents.judge.Judge.detect_stability",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "psalm.agents.judge.Judge.validate_batch_completeness",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "psalm.agents.juror.Juror.discuss",
            new=AsyncMock(return_value="I believe this infringes."),
        ),
        patch(
            "psalm.agents.juror.Juror.vote",
            new=AsyncMock(
                return_value=JurorVote(
                    juror_id="juror-0", vote="Guilty", rationale="Strong evidence."
                )
            ),
        ),
        patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)),
    ):
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .with_dimensions([CHARACTER])
            .with_debate(argumentation_rounds=1, deliberation_rounds=1, time_limit_seconds=60)
            .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
            .build()
        )
        result = await psalm.aevaluate(
            source_text=cases[0]["source"],
            target_text=cases[0]["target"],
        )

    assert isinstance(result, PSALMResult)
    assert result.verdict in {"Guilty", "Not Guilty", "Undecided"}
    assert result.rationale
    assert len(result.dimension_verdicts) == 1
    assert len(result.dimension_verdicts[0].argumentation_log.rounds) > 0
    assert len(result.dimension_verdicts[0].debate_log.rounds) > 0
    assert result.metadata.duration_seconds >= 0


async def test_identical_texts_returns_guilty_immediately():
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        psalm = await (
            PSALM()
            .with_prosecutor(**_agent_kwargs())
            .with_defense(**_agent_kwargs())
            .with_judge(**_agent_kwargs())
            .with_jury(_jury_configs())
            .build()
        )
    text = "The wizard had blue eyes."
    result = await psalm.aevaluate(source_text=text, target_text=text)
    assert result.verdict == "Guilty"
    assert result.metadata.argumentation_rounds_used == 0
