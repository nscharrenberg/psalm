# tests/unit/models/test_evidence.py
import pytest

from psalm.exceptions import PSALMRuntimeError
from psalm.models.evidence import Argument, Proof


@pytest.fixture
def proof():
    return Proof(
        source_excerpt="The wizard had bright blue eyes.",
        target_excerpt="The sorcerer possessed striking azure irises.",
        relevance="Both characters share a distinctive blue eye color trait.",
    )


def test_proof_creation(proof):
    assert proof.source_excerpt == "The wizard had bright blue eyes."
    assert proof.relevance.startswith("Both characters")


def test_argument_requires_at_least_one_proof(proof):
    arg = Argument(
        claim="Characters share unique physical traits.",
        dimension="character",
        proofs=[proof],
        agent_role="prosecutor",
        round=1,
    )
    assert len(arg.proofs) == 1


def test_argument_rejects_empty_proofs():
    with pytest.raises(PSALMRuntimeError) as exc_info:
        Argument(
            claim="Characters share traits.",
            dimension="character",
            proofs=[],
            agent_role="prosecutor",
            round=1,
        )
    assert exc_info.value.code == "PSALM-R003"
    assert "proof" in str(exc_info.value)


def test_argument_accepts_any_agent_role_from_llm(proof):
    # agent_role is stamped by code after the LLM call, so any LLM-returned
    # string must be accepted at model parse time — a validator here would
    # fire before the stamping code can run.
    arg = Argument(
        claim="Some claim.",
        dimension="character",
        proofs=[proof],
        agent_role="defense attorney",
        round=1,
    )
    assert arg.agent_role == "defense attorney"


def test_argument_accepts_multiple_proofs(proof):
    proof2 = Proof(
        source_excerpt="He wore a silver cloak.",
        target_excerpt="He was draped in a grey mantle.",
        relevance="Both characters wear similar silver/grey cloaks.",
    )
    arg = Argument(
        claim="Characters share appearance traits.",
        dimension="character",
        proofs=[proof, proof2],
        agent_role="defense",
        round=2,
    )
    assert len(arg.proofs) == 2
    assert arg.agent_role == "defense"


def test_argument_batch_defaults():
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch()
    assert batch.arguments == []
    assert batch.no_further_arguments is False
    assert batch.closing_statement is None


def test_argument_batch_with_arguments(proof):
    from psalm.models.evidence import ArgumentBatch
    arg = Argument(claim="c", dimension="character", proofs=[proof], agent_role="prosecutor", round=1)
    batch = ArgumentBatch(arguments=[arg])
    assert len(batch.arguments) == 1
    assert batch.no_further_arguments is False


def test_argument_batch_no_further_arguments_requires_closing_statement():
    from psalm.exceptions import PSALMRuntimeError
    from psalm.models.evidence import ArgumentBatch
    with pytest.raises(PSALMRuntimeError) as exc_info:
        ArgumentBatch(no_further_arguments=True)
    assert exc_info.value.code == "PSALM-R004"


def test_argument_batch_no_further_arguments_valid_with_statement():
    from psalm.models.evidence import ArgumentBatch
    batch = ArgumentBatch(no_further_arguments=True, closing_statement="Nothing further to add.")
    assert batch.no_further_arguments is True
    assert batch.closing_statement == "Nothing further to add."


def test_argument_batch_nonempty_arguments_auto_corrects_no_further_arguments(proof):
    # Some models conflate "no_further_arguments" (intended: zero arguments) with "this is my
    # final/complete batch" and set the flag alongside real arguments. Real, substantive
    # arguments are the stronger signal of intent — trust them and normalize the flag rather
    # than discarding genuinely useful output over a mislabeled boolean.
    from psalm.models.evidence import ArgumentBatch
    arg = Argument(claim="c", dimension="character", proofs=[proof], agent_role="prosecutor", round=1)
    batch = ArgumentBatch(arguments=[arg], no_further_arguments=True, closing_statement="Done.")
    assert batch.no_further_arguments is False
    assert len(batch.arguments) == 1
    # closing_statement is left as informational context, not cleared.
    assert batch.closing_statement == "Done."


def test_closing_statement_model():
    from psalm.models.evidence import ClosingStatement
    cs = ClosingStatement(round=1, statement="The prosecution rests.")
    assert cs.round == 1
    assert cs.statement == "The prosecution rests."


def test_argument_field_order():
    from psalm.models.evidence import Argument
    assert list(Argument.model_fields) == ["dimension", "proofs", "claim", "agent_role", "round"]
