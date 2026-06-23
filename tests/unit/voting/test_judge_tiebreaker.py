from unittest.mock import AsyncMock
import pytest
from psalm.exceptions import PSALMConfigError
from psalm.models.result import JurorVote
from psalm.voting.judge_tiebreaker import JudgeTiebreakerVoting


@pytest.fixture
def strategy():
    return JudgeTiebreakerVoting()


@pytest.fixture
def mock_judge(minimal_argumentation_log):
    judge = AsyncMock()
    judge.tiebreak = AsyncMock(return_value="Guilty")
    return judge


async def test_tiebreaker_calls_judge(strategy, mock_judge, minimal_argumentation_log):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="r1"),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="r2"),
    ]
    result = await strategy.apply(votes, judge=mock_judge, argumentation_log=minimal_argumentation_log)
    assert result.verdict == "Guilty"
    assert result.is_tie is False
    mock_judge.tiebreak.assert_called_once()


async def test_tiebreaker_never_returns_tie(strategy, mock_judge, minimal_argumentation_log):
    votes = [JurorVote(juror_id="j0", vote="Undecided", rationale="r1")]
    mock_judge.tiebreak = AsyncMock(return_value="Undecided")
    result = await strategy.apply(votes, judge=mock_judge, argumentation_log=minimal_argumentation_log)
    assert result.is_tie is False


async def test_tiebreaker_raises_without_judge(strategy, minimal_argumentation_log):
    votes = [JurorVote(juror_id="j0", vote="Guilty", rationale="r1")]
    with pytest.raises(PSALMConfigError) as exc_info:
        await strategy.apply(votes, judge=None, argumentation_log=minimal_argumentation_log)
    assert "PSALM-C005" in str(exc_info.value)
