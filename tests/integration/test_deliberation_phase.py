# tests/integration/test_deliberation_phase.py
import asyncio
from unittest.mock import AsyncMock

import pytest

from psalm.agents.judge import Judge
from psalm.agents.juror import Juror
from psalm.models.config import DebateConfig
from psalm.models.result import JurorVote
from psalm.phases.deliberation import DeliberationPhase
from psalm.voting.judge_tiebreaker import JudgeTiebreakerVoting
from psalm.voting.simple_majority import SimpleMajorityVoting
from psalm.voting.trust_weighted import TrustWeightedVoting


@pytest.fixture
def mock_jurors():
    jurors = []
    for i in range(3):
        j = AsyncMock(spec=Juror)
        j.juror_id = f"juror-{i}"
        j.discuss = AsyncMock(return_value=f"Juror {i}: I believe the evidence supports infringement.")
        j.vote = AsyncMock(return_value=JurorVote(juror_id=f"juror-{i}", vote="Guilty", rationale="Strong evidence."))
        jurors.append(j)
    return jurors


@pytest.fixture
def mock_judge():
    judge = AsyncMock(spec=Judge)
    judge.tiebreak = AsyncMock(return_value="Guilty")
    return judge


@pytest.fixture
def voting_strategies(mock_judge):
    return [
        SimpleMajorityVoting(),
        TrustWeightedVoting(),
        JudgeTiebreakerVoting(),
    ]


@pytest.fixture
def deliberation_phase(mock_jurors, voting_strategies, mock_judge):
    config = DebateConfig(rounds=3)
    return DeliberationPhase(
        jury=mock_jurors,
        voting_strategies=voting_strategies,
        judge=mock_judge,
        config=config,
    )


async def test_unanimous_verdict_first_round(deliberation_phase, minimal_argumentation_log):
    verdict, log = await deliberation_phase.run(minimal_argumentation_log)
    assert verdict == "Guilty"
    assert len(log.rounds) == 1


async def test_debate_log_contains_rounds(deliberation_phase, minimal_argumentation_log):
    verdict, log = await deliberation_phase.run(minimal_argumentation_log)
    assert len(log.rounds) > 0
    assert log.rounds[0].votes is not None


async def test_non_unanimous_triggers_more_rounds(mock_jurors, voting_strategies, mock_judge, minimal_argumentation_log):
    call_count = [0]

    async def split_then_agree(*args, **kwargs):
        call_count[0] += 1
        round_num = (call_count[0] - 1) // 3
        if round_num < 2:
            votes = ["Guilty", "Not Guilty", "Undecided"]
            juror_idx = (call_count[0] - 1) % 3
            return JurorVote(juror_id=f"juror-{juror_idx}", vote=votes[juror_idx], rationale="r")
        return JurorVote(juror_id="juror-0", vote="Not Guilty", rationale="On reflection, not infringing.")

    for j in mock_jurors:
        j.vote = split_then_agree

    config = DebateConfig(rounds=3)
    phase = DeliberationPhase(mock_jurors, voting_strategies, mock_judge, config)
    verdict, log = await phase.run(minimal_argumentation_log)
    assert len(log.rounds) > 1


async def test_jury_votes_in_parallel(mock_jurors, voting_strategies, mock_judge, minimal_argumentation_log):
    call_times = []

    async def record_time(*args, **kwargs):
        call_times.append(asyncio.get_running_loop().time())
        await asyncio.sleep(0.05)
        return JurorVote(juror_id="j", vote="Guilty", rationale="r")

    for j in mock_jurors:
        j.vote = record_time

    config = DebateConfig(rounds=1)
    phase = DeliberationPhase(mock_jurors, voting_strategies, mock_judge, config)
    await phase.run(minimal_argumentation_log)

    assert len(call_times) == 3
    time_spread = max(call_times) - min(call_times)
    assert time_spread < 0.03, f"Votes not parallel — spread was {time_spread:.3f}s"


async def test_exhausted_rounds_applies_voting_strategy(mock_jurors, voting_strategies, mock_judge, minimal_argumentation_log):
    async def always_split(juror_idx):
        async def _vote(*args, **kwargs):
            votes = ["Guilty", "Not Guilty", "Undecided"]
            return JurorVote(juror_id=f"juror-{juror_idx}", vote=votes[juror_idx], rationale="r")
        return _vote

    for i, j in enumerate(mock_jurors):
        j.vote = await always_split(i)

    mock_judge.tiebreak = AsyncMock(return_value="Undecided")
    config = DebateConfig(rounds=2)
    phase = DeliberationPhase(mock_jurors, voting_strategies, mock_judge, config)
    verdict, log = await phase.run(minimal_argumentation_log)
    assert verdict in {"Guilty", "Not Guilty", "Undecided"}
    assert len(log.rounds) == 2
