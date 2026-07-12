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
