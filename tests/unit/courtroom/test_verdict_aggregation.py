
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


def test_exception_dimension_low_score_barely_discounts():
    dvs = [
        _make_dv("character", Importance.HIGH, "Guilty", 0.9),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Not Guilty",
            weighted_score=0.1,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    # 0.9 * (1 - 0.1) = 0.81 — still comfortably above threshold.
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Guilty"


def test_exception_dimension_high_score_flips_verdict_to_not_guilty():
    dvs = [
        _make_dv("character", Importance.HIGH, "Not Guilty", 0.52),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Guilty",
            weighted_score=0.9,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    # 0.52 * (1 - 0.9) = 0.052 — the previously-decorative exception score now genuinely
    # discounts the infringement score, flipping a borderline verdict.
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Not Guilty"


def test_no_exception_dimension_selected_leaves_verdict_unchanged():
    # A single infringement dimension at weighted_score 0.52 with NO exception dimension
    # selected still resolves via the infringement score alone — the discount only applies
    # when the case actually selected an exception dimension.
    dvs = [_make_dv("character", Importance.HIGH, "Not Guilty", 0.52)]
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Guilty"


def test_exception_only_verdicts_is_undecided():
    from psalm.models.result import DimensionVerdict
    dvs = [
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Guilty",
            weighted_score=0.9,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Undecided"


def test_exception_critical_guilty_does_not_trigger_hard_override():
    from psalm.models.result import DimensionVerdict
    dvs = [
        _make_dv("character", Importance.HIGH, "Not Guilty", 0.1),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.CRITICAL,
            verdict="Guilty",
            weighted_score=0.95,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    # CRITICAL + Guilty must NOT trigger the hard override when it's an exception dimension —
    # only infringement dimensions can trigger it.
    assert _aggregate_verdict(dvs, guilty_threshold=0.5) == "Not Guilty"


def test_synthesize_rationale_labels_exception_dimensions():
    from psalm.models.result import DimensionVerdict
    dvs = [
        _make_dv("character", Importance.HIGH, "Guilty", 0.8),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Not Guilty",
            weighted_score=0.2,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    rationale = _synthesize_rationale("Guilty", dvs)
    assert "scenes-a-faire" in rationale
    assert "discounts infringement score" in rationale


def test_synthesize_rationale_shows_exception_discount_value():
    dvs = [
        _make_dv("character", Importance.HIGH, "Not Guilty", 0.52),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Guilty",
            weighted_score=0.9,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    rationale = _synthesize_rationale("Not Guilty", dvs)
    assert "Exception discount applied: 0.90" in rationale


def test_rationale_shows_exception_applies_label():
    dvs = [
        _make_dv("character", Importance.HIGH, "Not Guilty", 0.52),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Guilty",
            weighted_score=0.9,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    rationale = _synthesize_rationale("Not Guilty", dvs)
    assert "Exception Applies" in rationale


def test_rationale_shows_exception_does_not_apply_label():
    dvs = [
        _make_dv("character", Importance.HIGH, "Guilty", 0.9),
        DimensionVerdict(
            dimension="scenes-a-faire",
            dimension_type="exception",
            importance=Importance.MEDIUM,
            verdict="Not Guilty",
            weighted_score=0.1,
            argumentation_log=ArgumentationLog(rounds=[]),
            debate_log=DebateLog(rounds=[], final_voting_strategy_applied="unanimous"),
        ),
    ]
    rationale = _synthesize_rationale("Guilty", dvs)
    assert "Exception Does Not Apply" in rationale


def test_rationale_infringement_dimension_verdict_label_unchanged():
    # Infringement dimensions must still show plain "Guilty"/"Not Guilty" — only exception
    # dimensions get the Applies/Does Not Apply relabeling.
    dvs = [_make_dv("character", Importance.HIGH, "Not Guilty", 0.2)]
    rationale = _synthesize_rationale("Not Guilty", dvs)
    assert "character [high]: Not Guilty" in rationale
    assert "Applies" not in rationale
