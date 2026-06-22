# tests/unit/models/test_evidence.py
import pytest
from pydantic import ValidationError
from psalm.models.evidence import Proof, Argument


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
    with pytest.raises(ValidationError, match="at least one proof"):
        Argument(
            claim="Characters share traits.",
            dimension="character",
            proofs=[],
            agent_role="prosecutor",
            round=1,
        )


def test_argument_rejects_invalid_agent_role(proof):
    with pytest.raises(ValidationError, match="agent_role"):
        Argument(
            claim="Some claim.",
            dimension="character",
            proofs=[proof],
            agent_role="witness",
            round=1,
        )


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
