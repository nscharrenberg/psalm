from psalm.dimensions.base import (
    _IMPORTANCE_MULTIPLIERS,
    _SCORE_VALUES,
    Dimension,
    Importance,
    SimilarityScore,
    SubDimension,
)


def test_importance_multipliers():
    assert _IMPORTANCE_MULTIPLIERS[Importance.LOW] == 0.5
    assert _IMPORTANCE_MULTIPLIERS[Importance.MEDIUM] == 1.0
    assert _IMPORTANCE_MULTIPLIERS[Importance.HIGH] == 1.5
    assert _IMPORTANCE_MULTIPLIERS[Importance.CRITICAL] == 2.0


def test_importance_enum_values():
    assert Importance.LOW == "low"
    assert Importance.MEDIUM == "medium"
    assert Importance.HIGH == "high"
    assert Importance.CRITICAL == "critical"


def test_score_values():
    assert _SCORE_VALUES[SimilarityScore.NONE] == 0
    assert _SCORE_VALUES[SimilarityScore.GENERIC] == 1
    assert _SCORE_VALUES[SimilarityScore.POSSIBLE] == 2
    assert _SCORE_VALUES[SimilarityScore.CLEAR] == 3


def test_similarity_score_enum_values():
    assert SimilarityScore.NONE == "none"
    assert SimilarityScore.GENERIC == "generic"
    assert SimilarityScore.POSSIBLE == "possible"
    assert SimilarityScore.CLEAR == "clear"


def test_sub_dimension_defaults_to_medium():
    sd = SubDimension(name="Test Sub", description="A test sub-dimension.")
    assert sd.importance == Importance.MEDIUM


def test_sub_dimension_accepts_importance():
    sd = SubDimension(name="Test", description="desc", importance=Importance.CRITICAL)
    assert sd.importance == Importance.CRITICAL


def test_dimension_defaults_to_medium():
    dim = Dimension(
        name="test",
        description="A test dimension.",
        sub_dimensions=[SubDimension(name="Sub1", description="sub1")],
    )
    assert dim.importance == Importance.MEDIUM


def test_dimension_with_sub_dimensions():
    dim = Dimension(
        name="test",
        description="A test dimension.",
        importance=Importance.HIGH,
        sub_dimensions=[
            SubDimension(name="Sub1", description="sub1", importance=Importance.CRITICAL),
            SubDimension(name="Sub2", description="sub2", importance=Importance.LOW),
        ],
    )
    assert len(dim.sub_dimensions) == 2
    assert dim.sub_dimensions[0].importance == Importance.CRITICAL


def test_dimension_defaults_to_infringement_type():
    dim = Dimension(
        name="test",
        description="A test dimension.",
        sub_dimensions=[SubDimension(name="Sub1", description="sub1")],
    )
    assert dim.dimension_type == "infringement"


def test_dimension_accepts_exception_type():
    dim = Dimension(
        name="test-exception",
        description="A test exception dimension.",
        dimension_type="exception",
        sub_dimensions=[SubDimension(name="Sub1", description="sub1")],
    )
    assert dim.dimension_type == "exception"


def test_sub_dimension_inverse_defaults_to_false():
    sd = SubDimension(name="Test Sub", description="A test sub-dimension.")
    assert sd.inverse is False


def test_sub_dimension_accepts_inverse():
    sd = SubDimension(name="Test", description="desc", inverse=True)
    assert sd.inverse is True
