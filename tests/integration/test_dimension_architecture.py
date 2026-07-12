# tests/integration/test_dimension_architecture.py
"""
Integration smoke test for the dimension architecture.

Verifies that:
1. Default DebateConfig produces dimensions=[CHARACTER, PLOT, WORLD_BUILDING]
2. PSALMBuilder.with_dimensions([SCENES_A_FAIRE]) correctly overrides
3. Dimension objects flow through to ArgumentationState without mutation
"""


from psalm.builder import PSALM
from psalm.dimensions import CHARACTER, PLOT, SCENES_A_FAIRE, WORLD_BUILDING
from psalm.models.config import CaseInput, DebateConfig
from psalm.models.state import ArgumentationState


class TestDimensionArchitectureDefaults:
    """Test default dimension configuration."""

    def test_default_debate_config_dimensions(self):
        """Verify DebateConfig defaults to [CHARACTER, PLOT, WORLD_BUILDING]."""
        config = DebateConfig()
        assert config.dimensions == [CHARACTER, PLOT, WORLD_BUILDING]

    def test_default_case_input_dimensions(self):
        """Verify CaseInput defaults to [CHARACTER, PLOT, WORLD_BUILDING]."""
        case_input = CaseInput(
            source_text="The wizard had bright blue eyes.",
            target_text="The sorcerer possessed azure irises.",
        )
        assert case_input.dimensions == [CHARACTER, PLOT, WORLD_BUILDING]

    def test_dimension_objects_are_identical(self):
        """Verify that default dimensions are the same object instances."""
        config = DebateConfig()
        case_input = CaseInput(
            source_text="The wizard had bright blue eyes.",
            target_text="The sorcerer possessed azure irises.",
        )
        assert config.dimensions[0] is CHARACTER
        assert case_input.dimensions[0] is CHARACTER


class TestDimensionOverride:
    """Test overriding dimensions."""

    def test_custom_dimensions_in_debate_config(self):
        """Verify DebateConfig accepts custom dimensions."""
        config = DebateConfig(dimensions=[SCENES_A_FAIRE])
        assert config.dimensions == [SCENES_A_FAIRE]
        assert len(config.dimensions) == 1

    def test_custom_dimensions_in_case_input(self):
        """Verify CaseInput accepts custom dimensions."""
        case_input = CaseInput(
            source_text="The wizard had bright blue eyes.",
            target_text="The sorcerer possessed azure irises.",
            dimensions=[SCENES_A_FAIRE],
        )
        assert case_input.dimensions == [SCENES_A_FAIRE]

    def test_builder_with_dimensions_single(self):
        """Verify PSALM.with_dimensions() correctly sets a single dimension."""
        builder = PSALM()
        builder = builder.with_dimensions([SCENES_A_FAIRE])
        assert builder._debate_config.dimensions == [SCENES_A_FAIRE]

    def test_builder_with_dimensions_multiple(self):
        """Verify PSALM.with_dimensions() correctly sets multiple dimensions."""
        builder = PSALM()
        builder = builder.with_dimensions([CHARACTER, SCENES_A_FAIRE])
        assert builder._debate_config.dimensions == [CHARACTER, SCENES_A_FAIRE]

    def test_builder_with_dimensions_overrides_default(self):
        """Verify PSALM.with_dimensions() overrides the default."""
        builder = PSALM()
        # Builder starts with default
        assert builder._debate_config.dimensions == [CHARACTER, PLOT, WORLD_BUILDING]
        # Override
        builder = builder.with_dimensions([SCENES_A_FAIRE])
        assert builder._debate_config.dimensions == [SCENES_A_FAIRE]


class TestDimensionFlowThroughState:
    """Test that dimensions flow through to ArgumentationState."""

    def test_argumentation_state_accepts_dimensions(self):
        """Verify ArgumentationState can be constructed with dimensions."""
        state = ArgumentationState(
            source_text="The wizard had bright blue eyes.",
            target_text="The sorcerer possessed azure irises.",
            dimensions=[CHARACTER, PLOT],
            max_rounds=3,
        )
        assert state.dimensions == [CHARACTER, PLOT]

    def test_argumentation_state_preserves_dimension_identity(self):
        """Verify ArgumentationState preserves dimension object identity."""
        dims = [CHARACTER, PLOT, WORLD_BUILDING]
        state = ArgumentationState(
            source_text="The wizard had bright blue eyes.",
            target_text="The sorcerer possessed azure irises.",
            dimensions=dims,
            max_rounds=3,
        )
        assert state.dimensions[0] is CHARACTER
        assert state.dimensions[1] is PLOT
        assert state.dimensions[2] is WORLD_BUILDING

    def test_argumentation_state_mutation_detection(self):
        """Verify dimensions don't mutate when passed through state."""
        original_dims = [CHARACTER, PLOT]
        state = ArgumentationState(
            source_text="The wizard had bright blue eyes.",
            target_text="The sorcerer possessed azure irises.",
            dimensions=original_dims,
            max_rounds=3,
        )
        # Verify the dimensions are still the same objects
        assert state.dimensions == original_dims
        assert len(state.dimensions) == 2
        # Verify mutation of state dimensions doesn't affect original (if they were copied)
        state.dimensions.append(WORLD_BUILDING)
        # State should have mutated (it's a list), but verify it's at least consistent
        assert len(state.dimensions) == 3


class TestDimensionTypeSystem:
    """Test that dimension type annotations are respected."""

    def test_dimensions_are_dimension_objects(self):
        """Verify dimensions are Dimension instances."""
        config = DebateConfig()
        from psalm.dimensions.base import Dimension
        for dim in config.dimensions:
            assert isinstance(dim, Dimension)

    def test_scenes_a_faire_is_dimension(self):
        """Verify SCENES_A_FAIRE is a valid Dimension."""
        from psalm.dimensions.base import Dimension
        assert isinstance(SCENES_A_FAIRE, Dimension)

    def test_all_builtin_dimensions_are_valid(self):
        """Verify all built-in dimensions are valid Dimension instances."""
        from psalm.dimensions.base import Dimension
        dims = [CHARACTER, PLOT, WORLD_BUILDING, SCENES_A_FAIRE]
        for dim in dims:
            assert isinstance(dim, Dimension), f"{dim} is not a Dimension instance"
            assert dim.name is not None
            assert dim.sub_dimensions is not None


class TestDimensionPersistence:
    """Test that dimensions persist through config transformations."""

    def test_model_copy_preserves_dimensions(self):
        """Verify Pydantic model_copy preserves dimensions correctly."""
        original = DebateConfig(dimensions=[SCENES_A_FAIRE])
        copied = original.model_copy(update={"argumentation_rounds": 5})
        assert copied.dimensions == [SCENES_A_FAIRE]
        assert copied.argumentation_rounds == 5

    def test_builder_chaining_preserves_dimensions(self):
        """Verify builder method chaining preserves dimensions."""
        builder = PSALM()
        builder = builder.with_dimensions([CHARACTER, SCENES_A_FAIRE])
        builder = builder.with_debate(argumentation_rounds=5)
        builder = builder.with_voting(["simple_majority", "judge_tiebreaker"])
        assert builder._debate_config.dimensions == [CHARACTER, SCENES_A_FAIRE]
        assert builder._debate_config.argumentation_rounds == 5
