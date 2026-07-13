from unittest.mock import AsyncMock, patch

import pytest
from execution import TrialStartError, build_psalm, resolve_config
from schemas import AgentConfigRequest, JurorConfigRequest, TrialConfigRequest


def _config(**overrides) -> TrialConfigRequest:
    base = {
        "source_text": "source", "target_text": "target", "dimensions": ["Character"],
        "prosecutor": AgentConfigRequest(api_key="sk-p"),
        "defense": AgentConfigRequest(api_key="sk-d"),
        "judge": AgentConfigRequest(api_key="sk-j"),
        "jury": [JurorConfigRequest(api_key="sk-j0"), JurorConfigRequest(api_key="sk-j1"), JurorConfigRequest(api_key="sk-j2")],
    }
    base.update(overrides)
    return TrialConfigRequest(**base)


def test_resolve_config_resolves_all_roles_and_jury():
    resolved = resolve_config(_config())
    assert resolved["prosecutor"]["api_key"] == "sk-p"
    assert resolved["defense"]["api_key"] == "sk-d"
    assert resolved["judge"]["api_key"] == "sk-j"
    assert len(resolved["jury"]) == 3
    assert resolved["jury"][0]["api_key"] == "sk-j0"


def test_resolve_config_raises_trial_start_error_when_key_missing(monkeypatch):
    for key in ("PSALM_API_KEY", "PSALM_PROSECUTOR_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    config = _config(prosecutor=AgentConfigRequest())
    with pytest.raises(TrialStartError) as exc_info:
        resolve_config(config)
    assert exc_info.value.code == "PSALM-WEB-001"


async def test_build_psalm_raises_trial_start_error_for_unknown_dimension():
    config = _config(dimensions=["NotARealDimension"])
    resolved = resolve_config(config)
    with pytest.raises(TrialStartError) as exc_info:
        await build_psalm(config, resolved)
    assert exc_info.value.code == "PSALM-WEB-002"


async def test_build_psalm_raises_trial_start_error_for_unknown_strategy():
    config = _config(evaluation_strategy="not_a_real_strategy")
    resolved = resolve_config(config)
    with pytest.raises(TrialStartError) as exc_info:
        await build_psalm(config, resolved)
    assert exc_info.value.code == "PSALM-WEB-003"


async def test_build_psalm_returns_built_psalm_on_success():
    config = _config()
    resolved = resolve_config(config)
    with patch("psalm.builder.PSALM._ping_llm", new=AsyncMock(return_value=None)):
        result = await build_psalm(config, resolved)
    assert result is not None
    assert hasattr(result, "astream_evaluate")


async def test_build_psalm_wraps_config_error_from_llm_ping_failure():
    from psalm.exceptions import PSALMConfigError

    config = _config()
    resolved = resolve_config(config)
    ping_failure = AsyncMock(side_effect=PSALMConfigError(
        code="PSALM-C006", message="LLM connection failed for agent 'prosecutor'.", context={"role": "prosecutor"},
    ))
    with patch("psalm.builder.PSALM._ping_llm", new=ping_failure):
        with pytest.raises(TrialStartError) as exc_info:
            await build_psalm(config, resolved)
    assert exc_info.value.code == "PSALM-C006"
