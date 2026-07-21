# tests/unit/agents/test_defense.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.defense import Defense
from psalm.dimensions import CHARACTER, SCENES_A_FAIRE


@pytest.fixture
def defense(agent_config):
    return Defense(config=agent_config)


def test_defense_prompt_allows_affirmative_arguments():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "affirmative" in prompt or "proactive" in prompt or "you may also" in prompt


def test_defense_prompt_includes_idea_expression_doctrine():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "idea" in prompt and "expression" in prompt
    assert "unprotectable" in prompt or "not protected" in prompt


def test_defense_prompt_does_not_demand_strictly_verbatim():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "must include verbatim" not in prompt
    assert "passage" in prompt or "excerpt" in prompt or "quote" in prompt


def test_defense_system_prompt_forbids_padding_and_guesswork():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "unambiguous" in prompt
    assert "guess" in prompt or "speculative" in prompt
    assert "no_further_arguments" in prompt


async def test_defense_role(defense):
    assert defense.role == "defense"


async def test_gather_counter_arguments(defense, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(
            arguments=[sample_counter_argument], no_further_arguments=False, closing_statement=None
        )
    )

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        result = await defense.gather_counter_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=[CHARACTER],
            prosecutor_arguments=[sample_argument],
            round=1,
        )

    assert len(result.arguments) == 1
    assert result.arguments[0].agent_role == "defense"


async def test_defense_instruction_always_includes_both_types(defense, sample_argument):
    for prosecutor_arguments in [[], [sample_argument]]:
        captured: list = []

        async def capture_invoke(prompt, **kwargs):
            captured.extend(prompt)
            return MagicMock(arguments=[], no_further_arguments=False, closing_statement=None)

        mock_chain = MagicMock()
        mock_chain.ainvoke = capture_invoke
        mock_with_structured = MagicMock(return_value=mock_chain)
        captured.clear()
        with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
            await defense.gather_counter_arguments(
                "src", "tgt", [CHARACTER],
                prosecutor_arguments=prosecutor_arguments,
                round=1,
            )

        user_content = next(
            (m["content"] for m in captured if m["role"] == "user"), ""
        )
        label = "empty prosecution" if not prosecutor_arguments else "non-empty prosecution"
        assert (
            "affirmative" in user_content.lower()
            or "independently" in user_content.lower()
            or "proactive" in user_content.lower()
        ), f"Expected affirmative instruction with {label}: {user_content[:300]}"


async def test_counter_argument_includes_prosecutor_args_in_prompt(defense, sample_argument):
    captured_prompt = []

    async def capture_invoke(prompt, **kwargs):
        captured_prompt.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        await defense.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_argument], 1)

    user_content = next(m["content"] for m in captured_prompt if m["role"] == "user")
    assert "prosecutor" in user_content.lower() or "argument" in user_content.lower()


async def test_defense_gather_arguments_affirmative(defense, sample_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        result = await defense.gather_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=[CHARACTER],
            round=1,
        )
    assert len(result.arguments) == 1
    assert result.arguments[0].agent_role == "defense"


async def test_defense_gather_arguments_prompt_mentions_affirmative(defense, sample_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_arguments("src", "tgt", [CHARACTER], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "affirmative" in user_content.lower() or "distinct" in user_content.lower()


async def test_defense_counter_prompt_includes_sub_dimension_context(agent_config, sample_argument, sample_counter_argument):
    defense = Defense(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_counter_argument], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Identity & Properties" in user_content or "character" in user_content.lower()


async def test_defense_prompt_separates_infringement_and_exception_dimensions(agent_config, sample_argument):
    defense = Defense(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_arguments("src", "tgt", [CHARACTER, SCENES_A_FAIRE], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "PRIMARY DIMENSION (must argue): Character" in user_content
    assert "AVAILABLE EXCEPTION TOOLS" in user_content
    assert "Scènes à Faire" in user_content


async def test_defense_prompt_standalone_exception_dimension_is_mandatory(agent_config, sample_argument):
    # When an exception dimension runs its own standalone pipeline (no infringement dimension
    # present), it IS the subject of that pipeline's verdict and must be framed as mandatory —
    # not as an optional tool for a dimension that isn't even in the room.
    defense = Defense(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_arguments("src", "tgt", [SCENES_A_FAIRE], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "PRIMARY DIMENSION (must argue): Scènes à Faire" in user_content
    assert "AVAILABLE EXCEPTION TOOLS" not in user_content


async def test_defense_retry_hint_appears_in_prompt(agent_config, sample_argument):
    defense = Defense(config=agent_config)
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[sample_argument], no_further_arguments=False, closing_statement=None)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_arguments(
            "src", "tgt", [CHARACTER], 1, retry_hint="You must either argue or declare done."
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "You must either argue or declare done." in user_content


async def test_gather_arguments_returns_no_further_arguments(defense):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(
            arguments=[], no_further_arguments=True, closing_statement="The defense rests."
        )
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        result = await defense.gather_arguments("src", "tgt", [CHARACTER], 1)

    assert result.arguments == []
    assert result.no_further_arguments is True
    assert result.closing_statement == "The defense rests."


async def test_deliver_closing_argument_returns_string(defense, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(
        return_value=MagicMock(statement="The evidence clearly shows the target text is independently created.")
    )
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        result = await defense.deliver_closing_argument(
            dimensions=[CHARACTER],
            defense_counters=[sample_counter_argument],
            defense_arguments=[],
            prosecution_arguments=[sample_argument],
            prosecution_counters=[],
        )
    assert result == "The evidence clearly shows the target text is independently created."


async def test_deliver_closing_argument_prompt_includes_case_history(defense, sample_argument, sample_counter_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(statement="Closing.")

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.deliver_closing_argument(
            dimensions=[CHARACTER],
            defense_counters=[sample_counter_argument],
            defense_arguments=[],
            prosecution_arguments=[sample_argument],
            prosecution_counters=[],
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Both characters share unique physical traits." in user_content
    assert "Eye color is a generic trait not protected by copyright." in user_content


async def test_deliver_closing_argument_prompt_includes_proof_excerpts(defense, sample_counter_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(statement="Closing.")

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.deliver_closing_argument(
            dimensions=[CHARACTER],
            defense_counters=[sample_counter_argument],
            defense_arguments=[],
            prosecution_arguments=[],
            prosecution_counters=[],
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "The wizard had bright blue eyes." in user_content
    assert "The sorcerer possessed striking azure irises." in user_content


async def test_deliver_closing_argument_has_no_raw_text_access(defense, sample_counter_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(statement="Closing.")

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.deliver_closing_argument(
            dimensions=[CHARACTER],
            defense_counters=[sample_counter_argument],
            defense_arguments=[],
            prosecution_arguments=[],
            prosecution_counters=[],
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "SOURCE TEXT" not in user_content
    assert "TARGET TEXT" not in user_content
    assert "do not have access to the full source or target text" in user_content


async def test_deliver_closing_argument_empty_case_states_no_evidence(defense):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(statement="The defense has no surviving evidence to present.")

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.deliver_closing_argument(
            dimensions=[CHARACTER],
            defense_counters=[],
            defense_arguments=[],
            prosecution_arguments=[],
            prosecution_counters=[],
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "none survived judge validation" in user_content


def test_defense_prompt_exception_defenses_are_gated():
    from psalm.agents.defense import _SYSTEM_PROMPT
    assert "EXCEPTION-BASED DEFENSES" in _SYSTEM_PROMPT
    assert "AVAILABLE EXCEPTION TOOLS" in _SYSTEM_PROMPT
    normalized = " ".join(_SYSTEM_PROMPT.lower().split())
    assert "no exception-based defenses in this case" in normalized


def test_defense_prompt_primary_tools_no_longer_lead_with_idea_expression():
    from psalm.agents.defense import _SYSTEM_PROMPT
    assert "1. IDEA-EXPRESSION DICHOTOMY" not in _SYSTEM_PROMPT
    assert "1. LACK OF EXPRESSION-LEVEL SIMILARITY" in _SYSTEM_PROMPT


async def test_counter_instruction_does_not_unconditionally_offer_unprotectable_ideas(defense, sample_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(arguments=[], no_further_arguments=True, closing_statement="Nothing further.")

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(defense._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await defense.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_argument], 1)

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "unprotectable" not in user_content.lower()


def test_defense_prompt_specifies_proof_before_claim_order():
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "identify the specific textual proof first" in prompt
