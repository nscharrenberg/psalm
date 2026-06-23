import pytest
from psalm.models.result import JurorVote
from psalm.voting.trust_weighted import TrustWeightedVoting


@pytest.fixture
def strategy():
    return TrustWeightedVoting()


async def test_longer_rationale_wins_tie(strategy):
    votes = [
        JurorVote(
            juror_id="j0",
            vote="Guilty",
            rationale="The characters share blue eyes, silver cloaks, and a mentor relationship — three distinct protected traits.",
        ),
        JurorVote(
            juror_id="j1",
            vote="Not Guilty",
            rationale="No infringement.",
        ),
        JurorVote(
            juror_id="j2",
            vote="Guilty",
            rationale="Character and plot similarities are substantial.",
        ),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Guilty"
    assert result.is_tie is False


async def test_equal_weights_returns_tie(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Shared traits exist."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Independent creation strong."),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.is_tie is True


async def test_unanimous_with_weights(strategy):
    votes = [
        JurorVote(juror_id=f"j{i}", vote="Undecided", rationale="Borderline case with mixed evidence.")
        for i in range(3)
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Undecided"
    assert result.is_tie is False
