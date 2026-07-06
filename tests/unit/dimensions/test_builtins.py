from psalm.dimensions.base import Dimension, Importance
from psalm.dimensions.character import CHARACTER
from psalm.dimensions.plot import PLOT
from psalm.dimensions.scenes_a_faire import SCENES_A_FAIRE
from psalm.dimensions.world_building import WORLD_BUILDING


def test_character_is_valid_dimension():
    assert isinstance(CHARACTER, Dimension)
    assert CHARACTER.name == "character"
    assert CHARACTER.importance == Importance.HIGH
    assert len(CHARACTER.sub_dimensions) == 6


def test_character_has_high_identity_sub_dimension():
    names = {sd.name for sd in CHARACTER.sub_dimensions}
    assert "Identity & Properties" in names
    identity = next(sd for sd in CHARACTER.sub_dimensions if sd.name == "Identity & Properties")
    assert identity.importance == Importance.HIGH


def test_plot_is_valid_dimension():
    assert isinstance(PLOT, Dimension)
    assert PLOT.name == "plot"
    assert PLOT.importance == Importance.HIGH
    assert len(PLOT.sub_dimensions) == 6


def test_plot_has_critical_event_sequence():
    event_seq = next(sd for sd in PLOT.sub_dimensions if sd.name == "Event Sequence & Causality")
    assert event_seq.importance == Importance.CRITICAL


def test_world_building_is_valid_dimension():
    assert isinstance(WORLD_BUILDING, Dimension)
    assert WORLD_BUILDING.name == "world-building"
    assert WORLD_BUILDING.importance == Importance.MEDIUM
    assert len(WORLD_BUILDING.sub_dimensions) == 6


def test_scenes_a_faire_is_valid_dimension():
    assert isinstance(SCENES_A_FAIRE, Dimension)
    assert SCENES_A_FAIRE.name == "scenes-a-faire"
    assert SCENES_A_FAIRE.importance == Importance.MEDIUM
    assert len(SCENES_A_FAIRE.sub_dimensions) == 6


def test_scenes_a_faire_genre_conventions_is_critical():
    genre = next(sd for sd in SCENES_A_FAIRE.sub_dimensions if sd.name == "Genre Conventions & Setting")
    assert genre.importance == Importance.CRITICAL


def test_all_sub_dimensions_have_name_and_description():
    for dim in [CHARACTER, PLOT, WORLD_BUILDING, SCENES_A_FAIRE]:
        for sd in dim.sub_dimensions:
            assert sd.name
            assert sd.description
