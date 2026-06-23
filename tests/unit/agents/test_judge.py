from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from psalm.agents.judge import Judge
from psalm.models.result import ArgumentationLog, JurorVote, RoundArguments, ValidationResult


@pytest.fixture
def judge(agent_config):
    return Judge(config=agent_config)


async def test_judge_role(judge):
    assert judge.role == "judge"


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


async def test_should_cross_examine_with_discrepancy(judge, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(should_cross_examine=True))

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.should_cross_examine([sample_argument], [sample_counter_argument])

    assert result is True


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
