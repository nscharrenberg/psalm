import pytest
from pydantic import ValidationError
from psalm.models.evidence import Argument, Proof


def test_proof_creation():
    proof = Proof(
        source_excerpt="The hero had silver hair and ice-blue eyes.",
        target_excerpt="His hair was silver, eyes cold as ice.",
        relevance="Both describe identical physical traits in identical narrative role.",
    )
    assert proof.source_excerpt
    assert proof.target_excerpt
    assert proof.relevance


def test_argument_requires_at_least_one_proof():
    with pytest.raises(ValidationError, match="at least one proof"):
        Argument(
            claim="The defendant copied the protagonist's appearance.",
            proofs=[],
        )


def test_argument_with_one_proof():
    proof = Proof(
        source_excerpt="The hero had silver hair.",
        target_excerpt="His hair was silver.",
        relevance="Identical physical trait.",
    )
    argument = Argument(
        claim="The defendant copied the protagonist's appearance.",
        proofs=[proof],
    )
    assert len(argument.proofs) == 1
    assert argument.claim


def test_argument_with_multiple_proofs():
    proofs = [
        Proof(
            source_excerpt=f"excerpt {i}",
            target_excerpt=f"target {i}",
            relevance=f"relevance {i}",
        )
        for i in range(3)
    ]
    argument = Argument(claim="Multiple similarities exist.", proofs=proofs)
    assert len(argument.proofs) == 3


def test_proof_fields_required():
    with pytest.raises(ValidationError):
        Proof(source_excerpt="only source")
