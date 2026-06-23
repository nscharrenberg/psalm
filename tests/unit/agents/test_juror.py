from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from psalm.agents.juror import Juror
from psalm.models.result import JurorVote


@pytest.fixture
def juror(agent_config):
    return Juror(config=agent_config, juror_id="juror-0")


async def test_juror_role(juror):
    assert juror.role == "juror"


async def test_juror_id_stored(juror):
    assert juror.juror_id == "juror-0"


async def test_deliberate_returns_vote(juror, minimal_argumentation_log):
    mock_vote = JurorVote(juror_id="juror-0", vote="Guilty", rationale="Strong similarity.")
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_vote)

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(juror._llm), "with_structured_output", mock_with_structured):
        vote = await juror.deliberate(
            argumentation_log=minimal_argumentation_log,
            discussion_messages=[{"role": "juror-1", "content": "I agree with prosecution."}],
        )

    assert vote.vote in {"Guilty", "Not Guilty", "Undecided"}
    assert vote.juror_id == "juror-0"


async def test_deliberate_vote_includes_juror_id(juror, minimal_argumentation_log):
    mock_vote = JurorVote(juror_id="juror-99", vote="Not Guilty", rationale="No similarity.")
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_vote)

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(juror._llm), "with_structured_output", mock_with_structured):
        vote = await juror.deliberate(minimal_argumentation_log, [])

    assert vote.juror_id == "juror-0"  # override — always use self.juror_id
