from psalm.dimensions.base import Dimension, Importance
from psalm.dimensions.literature.exceptions.scenes_a_faire import SCENES_A_FAIRE
from psalm.dimensions.literature.narrative.character import CHARACTER
from psalm.dimensions.literature.narrative.plot import PLOT
from psalm.dimensions.literature.narrative.world_building import WORLD_BUILDING


def test_character_is_valid_dimension():
    assert isinstance(CHARACTER, Dimension)
    assert CHARACTER.name == "Character"
    assert CHARACTER.importance == Importance.HIGH
    assert len(CHARACTER.sub_dimensions) == 6


def test_character_has_high_identity_sub_dimension():
    names = {sd.name for sd in CHARACTER.sub_dimensions}
    assert "Character Identity & Traits" in names
    identity = next(sd for sd in CHARACTER.sub_dimensions if sd.name == "Character Identity & Traits")
    assert identity.importance == Importance.HIGH


def test_plot_is_valid_dimension():
    assert isinstance(PLOT, Dimension)
    assert PLOT.name == "Plot"
    assert PLOT.importance == Importance.HIGH
    assert len(PLOT.sub_dimensions) == 6


def test_plot_has_critical_event_sequence():
    event_seq = next(sd for sd in PLOT.sub_dimensions if sd.name == "Plot Event Sequence & Causality")
    assert event_seq.importance == Importance.CRITICAL


def test_world_building_is_valid_dimension():
    assert isinstance(WORLD_BUILDING, Dimension)
    assert WORLD_BUILDING.name == "World Building"
    assert WORLD_BUILDING.importance == Importance.HIGH
    assert len(WORLD_BUILDING.sub_dimensions) == 6


def test_scenes_a_faire_is_valid_dimension():
    assert isinstance(SCENES_A_FAIRE, Dimension)
    assert SCENES_A_FAIRE.name == "Scènes à Faire"
    assert SCENES_A_FAIRE.importance == Importance.HIGH
    assert len(SCENES_A_FAIRE.sub_dimensions) == 6


def test_scenes_a_faire_creative_elaboration_is_high():
    elaboration = next(
        sd for sd in SCENES_A_FAIRE.sub_dimensions if sd.name == "Creative Elaboration (INVERSE)"
    )
    assert elaboration.importance == Importance.HIGH


def test_all_sub_dimensions_have_name_and_description():
    for dim in [CHARACTER, PLOT, WORLD_BUILDING, SCENES_A_FAIRE]:
        for sd in dim.sub_dimensions:
            assert sd.name
            assert sd.description


def test_scenes_a_faire_is_exception_type():
    assert SCENES_A_FAIRE.dimension_type == "exception"


def test_character_plot_world_building_are_infringement_type():
    assert CHARACTER.dimension_type == "infringement"
    assert PLOT.dimension_type == "infringement"
    assert WORLD_BUILDING.dimension_type == "infringement"
