from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.juror import Juror, _format_argumentation_log, _format_prior_rounds
from psalm.dimensions import CHARACTER
from psalm.dimensions.base import SimilarityScore
from psalm.models.result import DimensionScore, JurorVote


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


async def test_discuss_returns_string(juror, minimal_argumentation_log):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(message="I think the evidence is strong."))
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(juror._llm), "with_structured_output", mock_with_structured):
        result = await juror.discuss(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[],
            current_discussion=[],
            round=1,
        )
    assert isinstance(result, str)
    assert len(result) > 0


async def test_vote_returns_juror_vote(juror, minimal_argumentation_log):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(vote="Guilty", rationale="Strong similarity.", dimension_scores=[])
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(juror._llm), "with_structured_output", mock_with_structured):
        result = await juror.vote(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[],
            discussion_messages=[],
            round=1,
            dimension=CHARACTER,
        )
    assert isinstance(result, JurorVote)
    assert result.juror_id == "juror-0"
    assert result.vote == "Guilty"


# --- Tests for context serialization helpers ---

def test_format_argumentation_log_includes_claims(minimal_argumentation_log):
    text = _format_argumentation_log(minimal_argumentation_log)
    assert "Both characters share unique physical traits." in text
    assert "The wizard had bright blue eyes." in text          # source_excerpt
    assert "The sorcerer possessed striking azure irises." in text  # target_excerpt
    assert "Eye color is a generic trait not protected by copyright." in text  # counter-arg claim


def test_format_argumentation_log_includes_round_header(minimal_argumentation_log):
    text = _format_argumentation_log(minimal_argumentation_log)
    assert "Round 1" in text
    assert "PROSECUTION" in text
    assert "DEFENSE" in text


def test_format_argumentation_log_includes_closing_statements():
    from psalm.models.result import ArgumentationLog, RoundArguments
    log = ArgumentationLog(
        rounds=[
            RoundArguments(
                round=1,
                prosecution_arguments=[],
                prosecution_closing_statement="The prosecution has no further arguments.",
                defense_counters=[],
                defense_counter_closing_statement="Nothing to counter.",
                defense_arguments=[],
                defense_closing_statement="The defense rests.",
                prosecution_counters=[],
                prosecution_counter_closing_statement="No rebuttal needed.",
            )
        ]
    )
    text = _format_argumentation_log(log)
    assert "The prosecution has no further arguments." in text
    assert "Nothing to counter." in text
    assert "The defense rests." in text
    assert "No rebuttal needed." in text


def test_format_argumentation_log_includes_closing_arguments():
    from psalm.models.result import ArgumentationLog
    log = ArgumentationLog(
        rounds=[],
        prosecution_closing_argument="The prosecution's final case for infringement.",
        defense_closing_argument="The defense's final case for independence.",
    )
    text = _format_argumentation_log(log)
    assert "The prosecution's final case for infringement." in text
    assert "The defense's final case for independence." in text


def test_format_argumentation_log_excludes_rejected_arguments():
    from psalm.models.evidence import Argument, Proof
    from psalm.models.result import ArgumentationLog, RejectedArgument, RoundArguments
    rejected_arg = Argument(
        claim="This claim was fabricated and rejected by the Judge.",
        dimension="character",
        proofs=[Proof(source_excerpt="src", target_excerpt="tgt", relevance="rel")],
        agent_role="prosecutor",
        round=1,
    )
    log = ArgumentationLog(
        rounds=[
            RoundArguments(
                round=1,
                prosecution_arguments=[],
                prosecution_rejected_arguments=[
                    RejectedArgument(argument=rejected_arg, rejection_reason="Fabricated excerpt.")
                ],
                defense_counters=[],
                defense_arguments=[],
                prosecution_counters=[],
            )
        ]
    )
    text = _format_argumentation_log(log)
    # Rejected arguments are audit-only — the jury must never see them.
    assert "This claim was fabricated and rejected by the Judge." not in text
    assert "Fabricated excerpt." not in text


def test_format_prior_rounds_includes_rationale_and_attribution():
    previous_rounds = [
        {
            "round": 1,
            "discussion_messages": [
                {"juror_id": "juror-0", "message": "The prosecution arguments are compelling."},
            ],
            "votes": [
                {"juror_id": "juror-0", "vote": "Guilty", "rationale": "Strong similarity found."},
                {"juror_id": "juror-1", "vote": "Not Guilty", "rationale": "Elements are generic."},
            ],
        }
    ]
    text = _format_prior_rounds(previous_rounds, "juror-0")
    assert "Strong similarity found." in text
    assert "Elements are generic." in text
    assert "(YOUR PRIOR VOTE)" in text
    assert "The prosecution arguments are compelling." in text


def test_format_prior_rounds_empty_returns_message():
    text = _format_prior_rounds([], "juror-0")
    assert "No prior" in text


def test_format_prior_rounds_marks_own_discussion():
    previous_rounds = [
        {
            "round": 1,
            "discussion_messages": [
                {"juror_id": "juror-0", "message": "I lean guilty."},
                {"juror_id": "juror-1", "message": "I lean not guilty."},
            ],
            "votes": [],
        }
    ]
    text = _format_prior_rounds(previous_rounds, "juror-0")
    assert "(YOU)" in text


# --- Tests that verify prompts contain actual argument content ---

async def test_discuss_prompt_contains_argument_content(juror, minimal_argumentation_log):
    captured: list = []

    async def mock_ainvoke(messages, **kwargs):
        captured.append(messages)
        return MagicMock(message="My view based on the evidence.")

    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(side_effect=mock_ainvoke)
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(juror._llm), "with_structured_output", mock_with_structured):
        await juror.discuss(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[],
            current_discussion=[],
            round=1,
        )

    assert captured, "LLM was not called"
    prompt_text = str(captured[0])
    assert "Both characters share unique physical traits." in prompt_text
    assert "The wizard had bright blue eyes." in prompt_text


def test_vote_prompt_frames_juror_as_argument_evaluator():
    # Jurors are lay evaluators — legal doctrine belongs to the attorneys.
    # The juror prompt should focus on burden of proof and argument quality, not legal doctrine.
    from psalm.agents.juror import _VOTE_SYSTEM_PROMPT
    prompt = _VOTE_SYSTEM_PROMPT.lower()
    assert "burden" in prompt
    assert "prosecution" in prompt


def test_discuss_prompt_frames_juror_as_argument_evaluator():
    from psalm.agents.juror import _DISCUSS_SYSTEM_PROMPT
    prompt = _DISCUSS_SYSTEM_PROMPT.lower()
    assert "burden" in prompt
    assert "prosecution" in prompt


async def test_vote_prompt_contains_prior_rationale(juror, minimal_argumentation_log):
    captured: list = []

    async def mock_ainvoke(messages, **kwargs):
        captured.append(messages)
        return MagicMock(vote="Guilty", rationale="Strong.", dimension_scores=[])

    previous_rounds = [
        {
            "round": 1,
            "discussion_messages": [],
            "votes": [
                {"juror_id": "juror-0", "vote": "Guilty", "rationale": "Strong similarity found."},
            ],
        }
    ]

    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(side_effect=mock_ainvoke)
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(juror._llm), "with_structured_output", mock_with_structured):
        await juror.vote(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=previous_rounds,
            discussion_messages=[],
            round=2,
            dimension=CHARACTER,
        )

    assert captured, "LLM was not called"
    prompt_text = str(captured[0])
    assert "Strong similarity found." in prompt_text
    assert "(YOUR PRIOR VOTE)" in prompt_text


# --- Tests for dimension-aware vote() and rubric prompt ---

async def test_juror_vote_accepts_dimension_parameter(agent_config, minimal_argumentation_log):
    from psalm.agents.juror import Juror
    from unittest.mock import AsyncMock, MagicMock, patch

    juror = Juror(config=agent_config, juror_id="juror-0")
    mock_vote = JurorVote(
        juror_id="juror-0",
        vote="Guilty",
        rationale="Clear similarities.",
        dimension_scores=[
            DimensionScore(
                sub_dimension="Identity & Properties",
                score=SimilarityScore.CLEAR,
                reasoning="Matching traits.",
            )
        ],
    )
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_vote)
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(juror._llm), "with_structured_output", mock_with_structured):
        result = await juror.vote(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[],
            discussion_messages=[],
            round=1,
            dimension=CHARACTER,
        )
    assert result.juror_id == "juror-0"
    assert result.vote == "Guilty"


async def test_juror_vote_prompt_includes_rubric_and_sub_dimensions(agent_config, minimal_argumentation_log):
    from psalm.agents.juror import Juror
    from unittest.mock import AsyncMock, MagicMock, patch

    juror = Juror(config=agent_config, juror_id="juror-0")
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return JurorVote(juror_id="juror-0", vote="Guilty", rationale="r.", dimension_scores=[])

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(juror._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await juror.vote(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[],
            discussion_messages=[],
            round=1,
            dimension=CHARACTER,
        )

    full_text = " ".join(m.get("content", "") for m in captured)
    assert "rubric" in full_text.lower() or "score" in full_text.lower()
    assert "Identity & Properties" in full_text
    assert "none" in full_text.lower() or "generic" in full_text.lower()


def test_juror_vote_system_prompt_has_rubric():
    from psalm.agents.juror import _VOTE_SYSTEM_PROMPT
    prompt = _VOTE_SYSTEM_PROMPT.lower()
    assert "rubric" in prompt or "score" in prompt
    assert "none" in prompt
    assert "generic" in prompt
    assert "possible" in prompt


def test_vote_prompt_grounds_verbatim_text_as_strong_evidence():
    # A juror seeing near-identical wording across a substantial passage should not be talked out
    # of "clear" by a defense label ("archetype", "unprotectable idea") that isn't actually backed
    # by differing wording — the prompt must say so explicitly, not leave it to the model's own
    # unguided judgment.
    from psalm.agents.juror import _VOTE_SYSTEM_PROMPT
    prompt = _VOTE_SYSTEM_PROMPT.lower()
    assert "identical" in prompt or "verbatim" in prompt
    assert "label" in prompt or "framing" in prompt


def test_vote_prompt_says_single_differing_detail_does_not_launder_whole_passage():
    from psalm.agents.juror import _VOTE_SYSTEM_PROMPT
    prompt = _VOTE_SYSTEM_PROMPT.lower()
    assert "single" in prompt or "one detail" in prompt or "renamed" in prompt
    assert "clear" in prompt


from psalm.dimensions import CHARACTER, PLOT


async def test_juror_vote_all_dimensions_returns_list(agent_config, minimal_argumentation_log):
    from psalm.agents.juror import Juror
    from psalm.models.result import JurorVote
    from unittest.mock import AsyncMock, MagicMock, patch

    juror = Juror(config=agent_config, juror_id="juror-0")
    mock_vote = JurorVote(juror_id="juror-0", vote="Guilty", rationale="r.", dimension_scores=[], dimension="character")
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_vote)
    with patch.object(type(juror._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        results = await juror.vote_all_dimensions(
            argumentation_log=minimal_argumentation_log,
            previous_rounds=[],
            discussion_messages=[],
            round=1,
            dimensions=[CHARACTER, PLOT],
        )
    assert len(results) == 2
    assert results[0].dimension == "character"
    assert results[1].dimension == "plot"


def test_juror_vote_has_optional_dimension_field():
    from psalm.models.result import JurorVote
    vote = JurorVote(juror_id="juror-0", vote="Guilty", rationale="r.")
    assert vote.dimension is None

    vote_with_dim = JurorVote(juror_id="juror-0", vote="Guilty", rationale="r.", dimension="character")
    assert vote_with_dim.dimension == "character"
