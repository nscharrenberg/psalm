import pytest
from psalm.exceptions import PSALMConfigError
from psalm.models.config import AgentConfig, DebateConfig


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
        AgentConfig(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o", temperature=3.0)
    assert exc_info.value.code == "PSALM-C007"
    assert "temperature" in str(exc_info.value)


def test_debate_config_defaults():
    config = DebateConfig()
    assert config.rounds == 5
    assert config.time_limit_seconds == 180
    assert "character" in config.dimensions
    assert config.voting_strategies[-1] == "judge_tiebreaker"


def test_debate_config_invalid_dimension():
    with pytest.raises(PSALMConfigError) as exc_info:
        DebateConfig(dimensions=["invalid_dim"])
    assert exc_info.value.code == "PSALM-C003"
    assert "invalid_dim" in str(exc_info.value)


def test_debate_config_invalid_voting_order():
    with pytest.raises(PSALMConfigError) as exc_info:
        DebateConfig(voting_strategies=["judge_tiebreaker", "simple_majority"])
    assert exc_info.value.code == "PSALM-C005"


def test_debate_config_unknown_voting_strategy():
    with pytest.raises(PSALMConfigError) as exc_info:
        DebateConfig(voting_strategies=["simple_majority", "ranked_choice"])
    assert exc_info.value.code == "PSALM-C004"
