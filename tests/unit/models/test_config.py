import pytest

from psalm.dimensions import CHARACTER, PLOT, WORLD_BUILDING
from psalm.dimensions.base import Dimension, SubDimension
from psalm.exceptions import PSALMConfigError
from psalm.models.config import AgentConfig, DebateConfig, CaseInput


def test_agent_config_minimal():
    config = AgentConfig(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    assert config.temperature == 0.7
    assert config.timeout_seconds == 180
    assert config.org_id is None


def test_agent_config_full():
    config = AgentConfig(
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        org_id="org-123",
        model="gpt-4o",
        temperature=0.0,
        max_tokens=1000,
        top_p=0.9,
        frequency_penalty=0.1,
        presence_penalty=0.1,
        seed=42,
        timeout_seconds=60,
    )
    assert config.seed == 42
    assert config.temperature == 0.0


def test_agent_config_invalid_temperature():
    with pytest.raises(PSALMConfigError) as exc_info:
        AgentConfig(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-4o",
            temperature=3.0,
        )
    assert exc_info.value.code == "PSALM-C007"
    assert "temperature" in str(exc_info.value)


def test_debate_config_defaults():
    config = DebateConfig()
    assert config.argumentation_rounds == 3
    assert config.deliberation_rounds == 2
    assert config.time_limit_seconds == 180
    dim_names = {d.name for d in config.dimensions}
    assert "character" in dim_names
    assert config.voting_strategies[-1] == "judge_tiebreaker"


def test_debate_config_invalid_voting_order():
    with pytest.raises(PSALMConfigError) as exc_info:
        DebateConfig(voting_strategies=["judge_tiebreaker", "simple_majority"])
    assert exc_info.value.code == "PSALM-C005"


def test_debate_config_unknown_voting_strategy():
    with pytest.raises(PSALMConfigError) as exc_info:
        DebateConfig(voting_strategies=["simple_majority", "ranked_choice"])
    assert exc_info.value.code == "PSALM-C004"


def test_debate_config_default_dimensions_are_dimension_objects():
    config = DebateConfig()
    assert len(config.dimensions) == 3
    assert all(isinstance(d, Dimension) for d in config.dimensions)
    names = {d.name for d in config.dimensions}
    assert names == {"character", "world-building", "plot"}


def test_debate_config_accepts_any_dimension_object():
    custom = Dimension(
        name="custom",
        description="A custom dimension.",
        sub_dimensions=[SubDimension(name="Sub1", description="sub1")],
    )
    config = DebateConfig(dimensions=[custom])
    assert config.dimensions[0].name == "custom"


def test_debate_config_accepts_scenes_a_faire():
    from psalm.dimensions import SCENES_A_FAIRE
    config = DebateConfig(dimensions=[CHARACTER, SCENES_A_FAIRE])
    assert len(config.dimensions) == 2


def test_case_input_default_dimensions_are_dimension_objects():
    ci = CaseInput(source_text="src", target_text="tgt")
    assert all(isinstance(d, Dimension) for d in ci.dimensions)
    assert len(ci.dimensions) == 3


def test_case_input_accepts_dimension_objects():
    ci = CaseInput(source_text="src", target_text="tgt", dimensions=[CHARACTER])
    assert ci.dimensions[0].name == "character"


def test_debate_config_default_evaluation_strategy():
    from psalm.models.config import DebateConfig, EvaluationStrategy
    config = DebateConfig()
    assert config.evaluation_strategy == EvaluationStrategy.FULLY_SEPARATE


def test_debate_config_evaluation_strategy_values():
    from psalm.models.config import EvaluationStrategy
    assert EvaluationStrategy.FULLY_SEPARATE == "fully_separate"
    assert EvaluationStrategy.SHARED_ARG_PER_DIM_DELIBERATION == "shared_arg_per_dim_deliberation"
    assert EvaluationStrategy.SHARED_ALL == "shared_all"


def test_debate_config_guilty_threshold_defaults():
    from psalm.models.config import DebateConfig
    config = DebateConfig()
    assert config.guilty_threshold == 0.5


def test_debate_config_accepts_custom_strategy():
    from psalm.models.config import DebateConfig, EvaluationStrategy
    config = DebateConfig(evaluation_strategy=EvaluationStrategy.SHARED_ALL)
    assert config.evaluation_strategy == EvaluationStrategy.SHARED_ALL
