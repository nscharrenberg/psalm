from unittest.mock import AsyncMock, MagicMock
import pytest
from psalm.models.config import DebateConfig
from psalm.models.result import ArgumentationLog, JurorVote
from psalm.models.state import DeliberationState
from psalm.phases.deliberation import DeliberationPhase


@pytest.fixture
def mock_juror():
    juror = MagicMock()
    juror.juror_id = "juror-0"
    juror.discuss = AsyncMock(return_value="I think the evidence supports infringement.")
    juror.vote = AsyncMock(
        return_value=JurorVote(juror_id="juror-0", vote="Guilty", rationale="Strong similarity.")
    )
    return juror


@pytest.fixture
def mock_judge():
    return MagicMock()


@pytest.fixture
def mock_voting_strategy():
    strategy = MagicMock()
    strategy.apply = AsyncMock(return_value=MagicMock(verdict="Guilty", is_tie=False))
    return strategy


@pytest.fixture
def deliberation_phase(mock_juror, mock_judge, mock_voting_strategy):
    return DeliberationPhase(
        jury=[mock_juror],
        voting_strategies=[mock_voting_strategy],
        judge=mock_judge,
        config=DebateConfig(),
    )


async def test_distribute_context_clears_state(deliberation_phase, minimal_argumentation_log):
    state = DeliberationState(
        argumentation_log=minimal_argumentation_log,
        max_rounds=2,
        discussion_messages=[{"juror_id": "juror-0", "message": "old message"}],
        current_round_votes=[{"juror_id": "juror-0", "vote": "Guilty", "rationale": "old"}],
    )
    result = await deliberation_phase._distribute_context(state)
    assert result["discussion_messages"] == []
    assert result["current_round_votes"] == []


async def test_jury_discussion_returns_messages(deliberation_phase, minimal_argumentation_log):
    state = DeliberationState(
        argumentation_log=minimal_argumentation_log,
        max_rounds=2,
    )
    result = await deliberation_phase._jury_discussion(state)
    messages = result["discussion_messages"]
    assert len(messages) == 1
    assert messages[0]["juror_id"] == "juror-0"
    assert isinstance(messages[0]["message"], str)


async def test_jury_vote_returns_votes(deliberation_phase, minimal_argumentation_log):
    state = DeliberationState(
        argumentation_log=minimal_argumentation_log,
        max_rounds=2,
    )
    result = await deliberation_phase._jury_vote(state)
    votes = result["current_round_votes"]
    assert len(votes) == 1
    assert votes[0]["juror_id"] == "juror-0"
    assert votes[0]["vote"] == "Guilty"


async def test_route_consensus_reached(deliberation_phase, minimal_argumentation_log):
    state = DeliberationState(
        argumentation_log=minimal_argumentation_log,
        max_rounds=2,
        consensus_reached=True,
    )
    route = deliberation_phase._route_after_consensus(state)
    assert route == "consensus"
