from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from psalm.agents.judge import Judge
from psalm.dimensions import CHARACTER, SCENES_A_FAIRE
from psalm.models.result import JurorVote, ValidationResult


@pytest.fixture
def judge(agent_config, run_execution):
    return Judge(config=agent_config, execution=run_execution)


async def test_judge_role(judge):
    assert judge.role == "judge"


def test_judge_validation_prompt_includes_idea_expression_criterion():
    # The prosecution validation prompt must check for expression-level vs idea-level similarity.
    from psalm.agents.judge import _PROSECUTION_VALIDATION_PROMPT
    prompt = _PROSECUTION_VALIDATION_PROMPT.lower()
    assert "idea" in prompt or "expression" in prompt or "unprotectable" in prompt
    assert "reject" in prompt or "invalid" in prompt


def test_judge_has_separate_defense_validation_prompt():
    # Defense arguments challenge prosecution claims — they argue differences, not similarity.
    # A separate validation prompt must exist, must require some kind of textual evidence
    # (passages/excerpts/proof), and must NOT require demonstrating similarity.
    from psalm.agents.judge import _DEFENSE_VALIDATION_PROMPT
    prompt = _DEFENSE_VALIDATION_PROMPT.lower()
    # Must ask for some form of evidence from the texts
    assert "passage" in prompt or "excerpt" in prompt or "proof" in prompt
    # Must not require demonstrating similarity (that's the prosecution's burden)
    assert "demonstrate similarity" not in prompt and "protected creative expression" not in prompt


async def test_validate_argument_accepts_role_parameter(judge, sample_argument):
    # validate_argument must accept a role parameter so defense and prosecution
    # arguments are evaluated under different standards.
    mock_result = ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(
            argument=sample_argument,
            source_text="The wizard had bright blue eyes.",
            target_text="The sorcerer possessed striking azure irises.",
            role="defense",
        )
    assert result.is_valid is True


async def test_validate_argument_valid(judge, sample_argument):
    mock_result = ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(
            argument=sample_argument,
            source_text="The wizard had bright blue eyes.",
            target_text="The sorcerer possessed striking azure irises.",
        )

    assert result.is_valid is True
    assert result.rejection_reason is None


async def test_validate_argument_invalid(judge, sample_argument):
    # The proofs are authentic (they match source_text/target_text below), so this exercises
    # the LLM coherence-check path, not the authenticity gate.
    mock_result = ValidationResult(
        reasoning="The cited proof shows the opposite of what the claim asserts.",
        is_valid=False,
        rejection_reason="Proof contradicts the claim.",
    )
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(
            sample_argument,
            "The wizard had bright blue eyes.",
            "The sorcerer possessed striking azure irises.",
        )

    assert result.is_valid is False
    assert "contradicts" in result.rejection_reason


async def test_validate_argument_rejects_inauthentic_proof_without_llm_call(judge):
    # A proof that doesn't genuinely appear in its text must be rejected deterministically,
    # without ever asking the LLM — this is the structural fix: the LLM never sees full-text
    # content it could wander into, because inauthentic proofs never reach it at all.
    from psalm.models.evidence import Argument, Proof
    arg = Argument(
        claim="Fabricated claim about content that isn't there.",
        dimension="character",
        proofs=[
            Proof(
                source_excerpt="This sentence does not exist anywhere in the source.",
                target_excerpt="Nor does this one exist in the target.",
                relevance="r",
            )
        ],
        agent_role="prosecutor",
        round=1,
    )
    mock_with_structured = MagicMock()
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(
            arg,
            "The wizard had bright blue eyes.",
            "The sorcerer possessed striking azure irises.",
        )

    assert result.is_valid is False
    assert "does not genuinely appear" in result.rejection_reason
    mock_with_structured.assert_not_called()


async def test_validate_argument_prompt_has_no_full_text_access(judge, sample_argument):
    # The LLM coherence-check call must never see the full source/target text — only the
    # argument's own claim and (already-verified-authentic) proofs. This is what prevents the
    # Judge from citing unrelated discrepancies elsewhere in the document.
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return ValidationResult(reasoning="The proofs support the claim.", is_valid=True)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.validate_argument(
            sample_argument,
            "Preamble the argument never cited. The wizard had bright blue eyes. Epilogue unrelated to this proof.",
            "Preamble the argument never cited. The sorcerer possessed striking azure irises. Epilogue unrelated to this proof.",
        )

    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "Preamble the argument never cited." not in user_content
    assert "Epilogue unrelated to this proof." not in user_content


async def test_tiebreak_returns_valid_verdict(judge, minimal_argumentation_log):
    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Strong evidence."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Weak similarity."),
    ]
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=MagicMock(verdict="Guilty"))

    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        verdict = await judge.tiebreak(votes, minimal_argumentation_log)

    assert verdict in {"Guilty", "Not Guilty", "Undecided"}


def test_prosecution_validation_prompt_does_not_reject_hedging_language():
    # The Judge must not police argument strength/certainty — only truthfulness. Weak or
    # interpretively-phrased arguments are the opposing side's job to rebut, not grounds
    # for the Judge to silently discard them.
    from psalm.agents.judge import _PROSECUTION_VALIDATION_PROMPT
    prompt = _PROSECUTION_VALIDATION_PROMPT.lower()
    assert "hedg" not in prompt
    assert "speculat" not in prompt


def test_defense_validation_prompt_does_not_reject_hedging_language():
    from psalm.agents.judge import _DEFENSE_VALIDATION_PROMPT
    prompt = _DEFENSE_VALIDATION_PROMPT.lower()
    assert "hedg" not in prompt
    assert "speculat" not in prompt


def test_is_proof_authentic_exact_match():
    from psalm.agents.judge import is_proof_authentic
    assert is_proof_authentic(
        "The wizard had blue eyes.", "Once upon a time, the wizard had blue eyes."
    ) is True


def test_is_proof_authentic_close_paraphrase_with_insertion():
    # Matches the real production pattern: near-identical text with one inserted phrase.
    from psalm.agents.judge import is_proof_authentic
    assert is_proof_authentic(
        "De opzichter, een Nederlander met een gezicht als een gesloten vuist, legde uit hoe het werkte",
        "De opzichter, een Nederlander met een gezicht als een gesloten vuist en een stem als "
        "schuurpapier, legde uit hoe het werkte",
    ) is True


def test_is_proof_authentic_ignores_whitespace_differences():
    from psalm.agents.judge import is_proof_authentic
    assert is_proof_authentic("The   wizard  had blue eyes.", "The wizard had blue eyes.") is True


def test_is_proof_authentic_rejects_fabricated_excerpt():
    from psalm.agents.judge import is_proof_authentic
    assert is_proof_authentic("The dragon breathed fire over the castle.", "The wizard had blue eyes.") is False


def test_is_proof_authentic_single_word_difference_still_authentic():
    # A single differing word (e.g. a character's name) elsewhere in an otherwise identical
    # passage does not make the excerpt inauthentic — authenticity is about whether the
    # excerpt genuinely exists in the text, not whether every word matches perfectly.
    from psalm.agents.judge import is_proof_authentic
    assert is_proof_authentic(
        "Ik herinner me een oude man, Pak Haji, die me op een avond vertelde over de tijd dat "
        "zijn dorp nog vrij was.",
        "Ik herinner me een oude man, Oom Rahmat, die me op een avond vertelde over de tijd dat "
        "zijn dorp nog vrij was.",
    ) is True


def test_prosecution_validation_prompt_rejects_self_contradicting_proofs():
    from psalm.agents.judge import _PROSECUTION_VALIDATION_PROMPT
    prompt = _PROSECUTION_VALIDATION_PROMPT.lower()
    assert "contradict" in prompt


def test_defense_validation_prompt_rejects_identical_text_as_distinctness_proof():
    # Citing an identical passage in both texts as "proof" that the texts are distinct is
    # self-contradicting — the evidence argues the opposite of the claim — and must be
    # rejectable on that narrow, factual basis (not lumped in with "weak arguments").
    from psalm.agents.judge import _DEFENSE_VALIDATION_PROMPT
    prompt = _DEFENSE_VALIDATION_PROMPT.lower()
    assert "contradict" in prompt
    assert "identical" in prompt


async def test_validate_batch_completeness_true_when_has_arguments(judge, sample_argument):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch(arguments=[sample_argument])
    assert await judge.validate_batch_completeness(batch) is True


async def test_validate_batch_completeness_true_when_no_further_arguments(judge):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further.")
    assert await judge.validate_batch_completeness(batch) is True


async def test_validate_batch_completeness_false_when_empty_and_not_declared(judge):
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch()
    assert await judge.validate_batch_completeness(batch) is False


async def test_defense_validation_rejects_unprotectable_idea_without_exception_dimension(judge):
    from psalm.models.evidence import Argument, Proof
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return ValidationResult(
            reasoning="No exception dimension covers this argument.",
            is_valid=False,
            rejection_reason="No exception dimension selected.",
        )

    arg = Argument(
        claim="This is an unprotectable idea / common archetype.",
        dimension="character",
        proofs=[Proof(source_excerpt="a", target_excerpt="a", relevance="r")],
        agent_role="defense",
        round=1,
    )
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.validate_argument(arg, "a", "a", role="defense", dimensions=[CHARACTER])

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "NO exception dimension is selected" in system_content
    assert "may NOT argue" in system_content


async def test_defense_validation_allows_exception_reasoning_when_dimension_selected(judge):
    from psalm.models.evidence import Argument, Proof
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return ValidationResult(reasoning="The exception dimension covers this argument.", is_valid=True)

    arg = Argument(
        claim="This is scenes à faire / unprotectable idea.",
        dimension="character",
        proofs=[Proof(source_excerpt="a", target_excerpt="a", relevance="r")],
        agent_role="defense",
        round=1,
    )
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.validate_argument(
            arg, "a", "a", role="defense", dimensions=[CHARACTER, SCENES_A_FAIRE],
        )

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "Scènes à Faire" in system_content
    assert "exception dimension(s)" in system_content


async def test_defense_validation_defaults_to_no_exceptions_when_dimensions_omitted(judge, sample_argument):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return ValidationResult(reasoning="The proofs support the claim.", is_valid=True)

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.validate_argument(
            sample_argument,
            "The wizard had bright blue eyes.",
            "The sorcerer possessed striking azure irises.",
            role="defense",
        )

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "NO exception dimension is selected" in system_content


async def test_prosecution_validation_ignores_dimensions_argument(judge, sample_argument):
    mock_result = ValidationResult(reasoning="The proofs support the claim.", is_valid=True)
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)
    mock_with_structured = MagicMock(return_value=mock_chain)
    with patch.object(type(judge._llm), "with_structured_output", mock_with_structured):
        result = await judge.validate_argument(
            sample_argument,
            "The wizard had bright blue eyes.",
            "The sorcerer possessed striking azure irises.",
            role="prosecution",
            dimensions=[CHARACTER],
        )
    assert result.is_valid is True


def test_tiebreak_decision_field_order():
    from psalm.agents.judge import _TiebreakDecision
    assert list(_TiebreakDecision.model_fields) == ["rationale", "verdict"]


def test_prosecution_validation_prompt_specifies_reasoning_before_conclusion():
    from psalm.agents.judge import _PROSECUTION_VALIDATION_PROMPT
    prompt = _PROSECUTION_VALIDATION_PROMPT.lower()
    assert "state your reasoning first" in prompt


def test_defense_validation_prompt_specifies_reasoning_before_conclusion():
    from psalm.agents.judge import _DEFENSE_VALIDATION_PROMPT
    prompt = _DEFENSE_VALIDATION_PROMPT.lower()
    assert "state your reasoning first" in prompt


async def test_tiebreak_prompt_specifies_reasoning_before_verdict(judge, minimal_argumentation_log):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(rationale="r.", verdict="Guilty")

    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Strong evidence."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Weak similarity."),
    ]
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.tiebreak(votes, minimal_argumentation_log)

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "explain your reasoning before stating the verdict" in system_content.lower()


async def test_tiebreak_infringement_dimension_has_no_exception_framing(judge, minimal_argumentation_log):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(rationale="r.", verdict="Guilty")

    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Strong evidence."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Weak similarity."),
    ]
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.tiebreak(votes, minimal_argumentation_log, dimension=CHARACTER)

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "EXCEPTION dimension" not in system_content


async def test_tiebreak_no_dimension_has_no_exception_framing(judge, minimal_argumentation_log):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(rationale="r.", verdict="Guilty")

    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Strong evidence."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Weak similarity."),
    ]
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.tiebreak(votes, minimal_argumentation_log)

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "EXCEPTION dimension" not in system_content


async def test_tiebreak_exception_dimension_has_exception_framing(judge, minimal_argumentation_log):
    captured: list = []

    async def capture_invoke(prompt, **kwargs):
        captured.extend(prompt)
        return MagicMock(rationale="r.", verdict="Guilty")

    votes = [
        JurorVote(juror_id="j0", vote="Guilty", rationale="Strong evidence."),
        JurorVote(juror_id="j1", vote="Not Guilty", rationale="Weak similarity."),
    ]
    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke
    with patch.object(type(judge._llm), "with_structured_output", MagicMock(return_value=mock_chain)):
        await judge.tiebreak(votes, minimal_argumentation_log, dimension=SCENES_A_FAIRE)

    system_content = next(m["content"] for m in captured if m["role"] == "system")
    assert "EXCEPTION dimension" in system_content
    assert 'Cast "Guilty" if the exception applies' in system_content
