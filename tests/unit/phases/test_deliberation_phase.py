from unittest.mock import AsyncMock, MagicMock

import pytest

from psalm.dimensions import CHARACTER
from psalm.dimensions.base import SimilarityScore
from psalm.models.config import DebateConfig
from psalm.models.result import DimensionScore, JurorVote
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
        current_dimension=CHARACTER,
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
        current_dimension=CHARACTER,
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
        current_dimension=CHARACTER,
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
        current_dimension=CHARACTER,
        consensus_reached=True,
    )
    route = deliberation_phase._route_after_consensus(state)
    assert route == "consensus"


@pytest.fixture
def mock_juror_with_scores():
    from psalm.models.result import JurorVote
    juror = MagicMock()
    juror.juror_id = "juror-0"
    juror.discuss = AsyncMock(return_value="I think the evidence supports infringement.")
    juror.vote = AsyncMock(
        return_value=JurorVote(
            juror_id="juror-0",
            vote="Guilty",
            rationale="Strong similarity.",
            dimension_scores=[
                DimensionScore(
                    sub_dimension="Identity & Properties",
                    score=SimilarityScore.CLEAR,
                    reasoning="Matching traits.",
                ),
                DimensionScore(
                    sub_dimension="Character Development",
                    score=SimilarityScore.POSSIBLE,
                    reasoning="Similar arc.",
                ),
            ],
        )
    )
    return juror


async def test_run_returns_weighted_score(mock_juror_with_scores, mock_judge, mock_voting_strategy, minimal_argumentation_log):
    phase = DeliberationPhase(
        jury=[mock_juror_with_scores],
        voting_strategies=[mock_voting_strategy],
        judge=mock_judge,
        config=DebateConfig(),
    )
    verdict, debate_log, weighted_score = await phase.run(minimal_argumentation_log, CHARACTER)
    assert isinstance(weighted_score, float)
    assert 0.0 <= weighted_score <= 1.0


async def test_vote_called_before_discussion_in_round_1(mock_juror_with_scores, mock_judge, mock_voting_strategy, minimal_argumentation_log):
    call_order: list[str] = []
    mock_juror_with_scores.vote = AsyncMock(
        side_effect=lambda **kwargs: (call_order.append("vote") or __import__("psalm.models.result", fromlist=["JurorVote"]).JurorVote(
            juror_id="juror-0", vote="Guilty", rationale="r.", dimension_scores=[]
        ))
    )
    mock_juror_with_scores.discuss = AsyncMock(
        side_effect=lambda **kwargs: (call_order.append("discuss") or "msg")
    )
    phase = DeliberationPhase(
        jury=[mock_juror_with_scores],
        voting_strategies=[mock_voting_strategy],
        judge=mock_judge,
        config=DebateConfig(deliberation_rounds=1),
    )
    await phase.run(minimal_argumentation_log, CHARACTER)
    # In a 1-round run that reaches consensus, vote happens but discuss may not
    # The key: vote must appear before discuss in the call order
    if "discuss" in call_order:
        assert call_order.index("vote") < call_order.index("discuss")


async def test_graph_entry_is_jury_vote(mock_juror, mock_judge, mock_voting_strategy, minimal_argumentation_log):
    phase = DeliberationPhase(
        jury=[mock_juror],
        voting_strategies=[mock_voting_strategy],
        judge=mock_judge,
        config=DebateConfig(),
    )
    # Patch _jury_discussion to detect if it's called before _jury_vote
    discussion_called_times: list[int] = []
    vote_called_times: list[int] = []
    tick = [0]

    original_vote = phase._jury_vote
    original_discuss = phase._jury_discussion

    async def tracking_vote(state):
        tick[0] += 1
        vote_called_times.append(tick[0])
        return await original_vote(state)

    async def tracking_discuss(state):
        tick[0] += 1
        discussion_called_times.append(tick[0])
        return await original_discuss(state)

    phase._jury_vote = tracking_vote
    phase._jury_discussion = tracking_discuss
    # Rebuild graph with patched methods
    phase._graph = phase._build_graph()

    await phase.run(minimal_argumentation_log, CHARACTER)

    assert len(vote_called_times) >= 1
    if discussion_called_times:
        assert vote_called_times[0] < discussion_called_times[0]
