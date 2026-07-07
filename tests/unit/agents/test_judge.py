from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.judge import Judge
from psalm.models.result import JurorVote, ValidationResult


@pytest.fixture
def judge(agent_config):
    return Judge(config=agent_config)


async def test_judge_role(judge):
    assert judge.role == "judge"


def test_judge_validation_prompt_includes_idea_expression_criterion():
    # The prosecution validation prompt must check for expression-level vs idea-level similarity.
    from psalm.agents.judge import _PROSECUTION_VALIDATION_PROMPT
    prompt = _PROSECUTION_VALIDATION_PROMPT.lower()
    assert "idea" in prompt or "expression" in prompt or "unprotectable" in prompt
    assert "reject" in prompt or "invalid" in prompt


def test_judge_has_separate_defense_validation_prompt():
    # Defense arguments challenge prosecution claims — they argue differences, not similarity.
    # A separate validation prompt must exist, must require some kind of textual evidence
    # (passages/excerpts/proof), and must NOT require demonstrating similarity.
    from psalm.agents.judge import _DEFENSE_VALIDATION_PROMPT
    prompt = _DEFENSE_VALIDATION_PROMPT.lower()
    # Must ask for some form of evidence from the texts
    assert "passage" in prompt or "excerpt" in prompt or "proof" in prompt
    # Must not require demonstrating similarity (that's the prosecution's burden)
    assert "demonstrate similarity" not in prompt and "protected creative expression" not in prompt


async def test_validate_argument_accepts_role_parameter(judge, sample_argument):
    # validate_argument must accept a role parameter so defense and prosecution
    # arguments are evaluated under different standards.
    mock_result = ValidationResult(is_valid=True)
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(
            argument=sample_argument,
            source_text="source",
            target_text="target",
            role="defense",
        )
    assert result.is_valid is True


async def test_validate_argument_valid(judge, sample_argument):
    mock_result = ValidationResult(is_valid=True)
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(
            argument=sample_argument,
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
        )

    assert result.is_valid is True
    assert result.rejection_reason is None


async def test_validate_argument_invalid(judge, sample_argument):
    mock_result = ValidationResult(is_valid=False, rejection_reason="Excerpts not verbatim.")
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(sample_argument, "src", "tgt")

    assert result.is_valid is False
    assert "verbatim" in result.rejection_reason


async def test_tiebreak_returns_valid_verdict(judge, minimal_argumentation_log):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Strong evidence."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Weak similarity."),
    ]
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(verdict="Guilty"))

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        verdict = await judge.tiebreak(votes, minimal_argumentation_log)

    assert verdict in {"Guilty", "Not Guilty", "Undecided"}


def test_prosecution_validation_prompt_rejects_hedging_language():
    from psalm.agents.judge import _PROSECUTION_VALIDATION_PROMPT
    prompt = _PROSECUTION_VALIDATION_PROMPT.lower()
    assert "hedg" in prompt or "speculat" in prompt
    assert "might" in prompt or "possibly" in prompt


def test_defense_validation_prompt_rejects_hedging_language():
    from psalm.agents.judge import _DEFENSE_VALIDATION_PROMPT
    prompt = _DEFENSE_VALIDATION_PROMPT.lower()
    assert "hedg" in prompt or "speculat" in prompt


async def test_validate_batch_completeness_true_when_has_arguments(judge, sample_argument):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch(arguments=[sample_argument])
    assert await judge.validate_batch_completeness(batch) is True


async def test_validate_batch_completeness_true_when_no_further_arguments(judge):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")
    assert await judge.validate_batch_completeness(batch) is True


async def test_validate_batch_completeness_false_when_empty_and_not_declared(judge):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch()
    assert await judge.validate_batch_completeness(batch) is False
