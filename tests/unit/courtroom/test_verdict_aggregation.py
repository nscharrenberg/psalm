import pytest

from psalm.courtroom.default import _aggregate_verdict, _synthesize_rationale
from psalm.dimensions.base import Importance
from psalm.models.result import ArgumentationLog, DebateLog, DimensionVerdict


def _make_dv(
    dimension: str,
    importance: Importance,
    verdict: str,
    weighted_score: float,
) -> DimensionVerdict:
    return DimensionVerdict(
        dimension=dimension,
        importance=importance,
        verdict=verdict,
        weighted_score=weighted_score,
        argumentation_log=ArgumentationLog(rounds=[]),
        debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
    )


def test_aggregate_guilty_when_score_above_threshold():
    dvs = [_make_dv("character", Importance.HIGH, "Guilty", 0.8)]
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Guilty"


def test_aggregate_not_guilty_when_score_below_threshold():
    dvs = [_make_dv("character", Importance.HIGH, "Not Guilty", 0.2)]
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Not Guilty"


def test_aggregate_critical_guilty_overrides_low_score():
    dvs = [
        _make_dv("plot", Importance.CRITICAL, "Guilty", 0.1),   # CRITICAL + Guilty → override
        _make_dv("character", Importance.HIGH, "Not Guilty", 0.0),
    ]
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Guilty"


def test_aggregate_critical_not_guilty_does_not_override():
    dvs = [
        _make_dv("plot", Importance.CRITICAL, "Not Guilty", 0.0),
        _make_dv("character", Importance.HIGH, "Guilty", 0.9),
    ]
    result = _aggregate_verdict(dvs, guilty_threshold=0.5)
    # character (HIGH, 0.9×1.5=1.35) vs plot (CRITICAL, 0.0×2.0=0.0) → normalised = 1.35/3.5 ≈ 0.386
    assert result == "Not Guilty"


def test_aggregate_empty_verdicts_is_undecided():
    assert _aggregate_verdict([], guilty_threshold=0.5) == "Undecided"


def test_aggregate_weighted_by_importance():
    # HIGH (1.5×) at 1.0 and LOW (0.5×) at 0.0 → (1.5+0)/(1.5+0.5) = 0.75 → Guilty
    dvs = [
        _make_dv("character", Importance.HIGH, "Guilty", 1.0),
        _make_dv("world-building", Importance.LOW, "Not Guilty", 0.0),
    ]
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Guilty"


def test_synthesize_rationale_contains_dimension_names():
    dvs = [
        _make_dv("character", Importance.HIGH, "Guilty", 0.8),
        _make_dv("plot", Importance.HIGH, "Not Guilty", 0.2),
    ]
    rationale = _synthesize_rationale("Guilty", dvs)
    assert "character" in rationale
    assert "plot" in rationale
    assert "Guilty" in rationale
