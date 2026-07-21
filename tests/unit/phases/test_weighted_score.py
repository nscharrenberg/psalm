from psalm.dimensions import CHARACTER
from psalm.dimensions.base import SimilarityScore
from psalm.models.result import DimensionScore, JurorVote
from psalm.phases.deliberation import _compute_weighted_score


def _vote(scores: list[tuple[str, SimilarityScore]]) -> JurorVote:
    return JurorVote(
        juror_id="juror-0",
        vote="Guilty",
        rationale="r.",
        dimension_scores=[
            DimensionScore(sub_dimension=name, score=score, reasoning="r.")
            for name, score in scores
        ],
    )


def test_all_clear_scores_gives_max_normalised():
    votes = [
        _vote([(sd.name, SimilarityScore.CLEAR) for sd in CHARACTER.sub_dimensions])
    ]
    score = _compute_weighted_score(votes, CHARACTER)
    assert abs(score - 1.0) < 1e-6


def test_all_none_scores_gives_zero():
    votes = [
        _vote([(sd.name, SimilarityScore.NONE) for sd in CHARACTER.sub_dimensions])
    ]
    score = _compute_weighted_score(votes, CHARACTER)
    assert score == 0.0


def test_no_votes_gives_zero():
    score = _compute_weighted_score([], CHARACTER)
    assert score == 0.0


def test_score_between_zero_and_one():
    sub_names = [sd.name for sd in CHARACTER.sub_dimensions]
    votes = [
        _vote([
            (sub_names[0], SimilarityScore.CLEAR),
            (sub_names[1], SimilarityScore.POSSIBLE),
            (sub_names[2], SimilarityScore.GENERIC),
            (sub_names[3], SimilarityScore.NONE),
            (sub_names[4], SimilarityScore.NONE),
            (sub_names[5], SimilarityScore.NONE),
        ])
    ]
    score = _compute_weighted_score(votes, CHARACTER)
    assert 0.0 < score < 1.0


def test_multiple_jurors_averaged():
    identity_name = CHARACTER.sub_dimensions[0].name
    votes = [
        _vote([(identity_name, SimilarityScore.CLEAR)] +
              [(sd.name, SimilarityScore.NONE) for sd in CHARACTER.sub_dimensions[1:]]),
        _vote([(identity_name, SimilarityScore.NONE)] +
              [(sd.name, SimilarityScore.NONE) for sd in CHARACTER.sub_dimensions[1:]]),
    ]
    score = _compute_weighted_score(votes, CHARACTER)
    # Two jurors: one CLEAR (3), one NONE (0) for identity (HIGH=1.5x) → avg 1.5
    # All others are 0, so numerator ≈ 1.5, denominator = high importance weight
    assert score > 0.0
    assert score < 0.5  # Should be relatively small since only one sub-dim has any score


def test_inverse_sub_dimension_clear_score_contributes_zero():
    from psalm.dimensions.base import Dimension, Importance, SubDimension
    dim = Dimension(
        name="test-exception",
        description="A test exception dimension with one inverted sub-dimension.",
        dimension_type="exception",
        sub_dimensions=[
            SubDimension(name="Inverted Sub", description="d.", importance=Importance.HIGH, inverse=True),
        ],
    )
    votes = [_vote([("Inverted Sub", SimilarityScore.CLEAR)])]
    score = _compute_weighted_score(votes, dim)
    # clear (avg=3) on an inverted sub-dimension flips to (3 - 3) = 0 contribution.
    assert score == 0.0


def test_inverse_sub_dimension_none_score_contributes_max():
    from psalm.dimensions.base import Dimension, Importance, SubDimension
    dim = Dimension(
        name="test-exception",
        description="A test exception dimension with one inverted sub-dimension.",
        dimension_type="exception",
        sub_dimensions=[
            SubDimension(name="Inverted Sub", description="d.", importance=Importance.HIGH, inverse=True),
        ],
    )
    votes = [_vote([("Inverted Sub", SimilarityScore.NONE)])]
    score = _compute_weighted_score(votes, dim)
    # none (avg=0) on an inverted sub-dimension flips to (3 - 0) = 3 contribution, the max
    # possible for this sub-dimension -- normalised score is 1.0.
    assert abs(score - 1.0) < 1e-6


def test_mixed_normal_and_inverse_sub_dimensions_blend_correctly():
    from psalm.dimensions.base import Dimension, Importance, SubDimension
    dim = Dimension(
        name="test-exception",
        description="A test exception dimension mixing normal and inverted sub-dimensions.",
        dimension_type="exception",
        sub_dimensions=[
            SubDimension(name="Normal Sub", description="d.", importance=Importance.MEDIUM, inverse=False),
            SubDimension(name="Inverted Sub", description="d.", importance=Importance.MEDIUM, inverse=True),
        ],
    )
    votes = [_vote([("Normal Sub", SimilarityScore.CLEAR), ("Inverted Sub", SimilarityScore.CLEAR)])]
    score = _compute_weighted_score(votes, dim)
    # Normal Sub: clear (avg=3) contributes 3 * 1.0 = 3.
    # Inverted Sub: clear (avg=3) flips to (3-3) = 0, contributes 0 * 1.0 = 0.
    # weighted_total = 3, max_possible = 3*1.0 + 3*1.0 = 6 -> normalised = 0.5.
    assert abs(score - 0.5) < 1e-6
