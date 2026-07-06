# tests/unit/agents/test_defense.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.defense import Defense
from psalm.dimensions import CHARACTER


@pytest.fixture
def defense(agent_config):
    return Defense(config=agent_config)


def test_defense_prompt_allows_affirmative_arguments():
    # Defense should not only react to prosecution — it can also make affirmative claims
    # that prosecution can rebut in subsequent rounds.
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "affirmative" in prompt or "proactive" in prompt or "you may also" in prompt


def test_defense_prompt_includes_idea_expression_doctrine():
    # Defense carries the EU idea-expression dichotomy — it is their primary legal tool.
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "idea" in prompt and "expression" in prompt
    assert "unprotectable" in prompt or "not protected" in prompt


def test_defense_prompt_does_not_demand_strictly_verbatim():
    # "MUST include verbatim excerpts" causes agents to return empty when they cannot find
    # perfect word-for-word matches. The prompt must allow approximate quotes.
    from psalm.agents.defense import _SYSTEM_PROMPT
    prompt = _SYSTEM_PROMPT.lower()
    assert "must include verbatim" not in prompt
    # Should still ask for relevant passages
    assert "passage" in prompt or "excerpt" in prompt or "quote" in prompt


async def test_defense_role(defense):
    assert defense.role == "defense"


async def test_gather_counter_arguments(defense, sample_argument, sample_counter_argument):
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(arguments=[sample_counter_argument]))

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        result = await defense.gather_counter_arguments(
            source_text="The wizard had blue eyes.",
            target_text="The sorcerer had azure eyes.",
            dimensions=[CHARACTER],
            prosecutor_arguments=[sample_argument],
            round=1,
        )

    assert len(result) == 1
    assert result[0].agent_role == "defense"


async def test_defense_instruction_always_includes_both_types(defense, sample_argument):
    # Defense must always encourage BOTH counter-arguments (when prosecution argued) AND
    # affirmative arguments about why the texts are independently created — regardless of
    # whether prosecution produced anything. This makes the debate symmetric.
    for prosecutor_arguments in [[], [sample_argument]]:
        captured: list = []

        async def capture_invoke(prompt, **kwargs):
            captured.extend(prompt)
            return MagicMock(arguments=[])

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

    async def capture_invoke(prompt):
        captured_prompt.extend(prompt)
        return MagicMock(arguments=[sample_argument])

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(defense._llm), "with_structured_output", mock_with_structured):
        await defense.gather_counter_arguments("src", "tgt", [CHARACTER], [sample_argument], 1)

    user_content = next(m["content"] for m in captured_prompt if m["role"] == "user")
    assert "prosecutor" in user_content.lower() or "argument" in user_content.lower()
