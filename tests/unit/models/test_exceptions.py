# tests/unit/models/test_exceptions.py
import pytest

from psalm.exceptions import (
    PSALMAgentError,
    PSALMConfigError,
    PSALMError,
    PSALMRuntimeError,
    PSALMValidationError,
)


def test_psalm_error_formats_message():
    err = PSALMConfigError(
        code="PSALM-C002",
        message="Jury requires a minimum of 3 members, got 2.",
        context={"jury_size": 2, "minimum_required": 3},
        suggestion="Add at least one more AgentConfig to .with_jury([...]).",
    )
    rendered = str(err)
    assert "PSALM-C002" in rendered
    assert "Jury requires" in rendered
    assert "jury_size" in rendered
    assert "Add at least" in rendered


def test_psalm_error_is_base_for_all():
    assert issubclass(PSALMConfigError, PSALMError)
    assert issubclass(PSALMValidationError, PSALMError)
    assert issubclass(PSALMRuntimeError, PSALMError)
    assert issubclass(PSALMAgentError, PSALMError)


def test_psalm_error_wraps_cause():
    original = ValueError("original error")
    err = PSALMAgentError(
        code="PSALM-A001",
        message="LLM call failed.",
        context={"model": "gpt-4o"},
        suggestion="Check API credentials.",
        cause=original,
    )
    assert err.cause is original


def test_psalm_error_empty_context():
    err = PSALMConfigError(code="PSALM-C001", message="Missing agent.")
    assert err.context == {}
    assert err.suggestion == ""
    assert err.cause is None


def test_error_can_be_caught_as_base():
    with pytest.raises(PSALMError):
        raise PSALMConfigError(code="PSALM-C001", message="Missing agent.")
