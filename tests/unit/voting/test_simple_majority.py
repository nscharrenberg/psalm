import pytest
from psalm.models.result import JurorVote
from psalm.voting.simple_majority import SimpleMajorityVoting


@pytest.fixture
def strategy():
    return SimpleMajorityVoting()


async def test_unanimous_guilty(strategy):
    votes = [
        JurorVote(juror_id=f"j{i}", vote="Guilty", rationale="Clear infringement.")
        for i in range(3)
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Guilty"
    assert result.is_tie is False


async def test_majority_not_guilty(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Not Guilty", rationale="No infringement."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Independent creation."),
        JurorVote(juror_id="j2", vote="Guilty", rationale="Some similarity."),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Not Guilty"
    assert result.is_tie is False


async def test_exact_tie_returns_is_tie(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Infringing."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Not infringing."),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.is_tie is True
    assert result.verdict is None


async def test_three_way_split_returns_is_tie(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="r1"),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="r2"),
        JurorVote(juror_id="j2", vote="Undecided", rationale="r3"),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.is_tie is True


async def test_majority_undecided(strategy):
    votes = [
        JurorVote(juror_id="j0", vote="Undecided", rationale="Borderline."),
        JurorVote(juror_id="j1", vote="Undecided", rationale="Borderline."),
        JurorVote(juror_id="j2", vote="Guilty", rationale="Infringing."),
    ]
    result = await strategy.apply(votes, judge=None)
    assert result.verdict == "Undecided"
    assert result.is_tie is False
