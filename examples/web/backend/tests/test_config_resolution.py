import os

import pytest

from config_resolution import resolve_agent_config, resolve_juror_config, resolve_value


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("PSALM_"):
            monkeypatch.delenv(key, raising=False)


def test_resolve_value_prefers_posted_value():
    assert resolve_value("posted", "PSALM_UNUSED") == "posted"


def test_resolve_value_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("PSALM_TEST_VAR", "from-env")
    assert resolve_value(None, "PSALM_TEST_VAR") == "from-env"


def test_resolve_value_falls_back_to_default_when_nothing_set():
    assert resolve_value(None, "PSALM_TEST_VAR", default="fallback") == "fallback"


def test_resolve_value_treats_empty_string_as_unset(monkeypatch):
    monkeypatch.setenv("PSALM_TEST_VAR", "from-env")
    assert resolve_value("", "PSALM_TEST_VAR") == "from-env"


def test_resolve_agent_config_uses_posted_fields():
    cfg = resolve_agent_config(
        "PROSECUTOR",
        {"base_url": "https://custom/v1", "api_key": "sk-posted", "model": "gpt-4o", "temperature": 0.5},
    )
    assert cfg == {
        "base_url": "https://custom/v1", "api_key": "sk-posted", "model": "gpt-4o", "temperature": 0.5,
    }


def test_resolve_agent_config_falls_back_to_role_env_var(monkeypatch):
    monkeypatch.setenv("PSALM_PROSECUTOR_API_KEY", "sk-role-env")
    cfg = resolve_agent_config("PROSECUTOR", {})
    assert cfg["api_key"] == "sk-role-env"
    assert cfg["base_url"] == "https://api.openai.com/v1"
    assert cfg["model"] == "gpt-4o-mini"
    assert cfg["temperature"] == 0.1


def test_resolve_agent_config_role_env_var_takes_priority_over_global(monkeypatch):
    monkeypatch.setenv("PSALM_API_KEY", "sk-global")
    monkeypatch.setenv("PSALM_PROSECUTOR_API_KEY", "sk-role")
    cfg = resolve_agent_config("PROSECUTOR", {})
    assert cfg["api_key"] == "sk-role"


def test_resolve_agent_config_falls_back_to_global_env_var(monkeypatch):
    monkeypatch.setenv("PSALM_API_KEY", "sk-global")
    cfg = resolve_agent_config("DEFENSE", {})
    assert cfg["api_key"] == "sk-global"


def test_resolve_agent_config_raises_when_no_key_available():
    with pytest.raises(ValueError, match="PROSECUTOR"):
        resolve_agent_config("PROSECUTOR", {})


def test_resolve_juror_config_uses_posted_fields():
    cfg = resolve_juror_config(
        0, {"base_url": "https://custom/v1", "api_key": "sk-posted", "model": "gpt-4o", "temperature": 0.2, "seed": 7},
    )
    assert cfg == {
        "base_url": "https://custom/v1", "api_key": "sk-posted", "model": "gpt-4o",
        "temperature": 0.2, "seed": 7,
    }


def test_resolve_juror_config_seed_defaults_to_index():
    cfg = resolve_juror_config(2, {"api_key": "sk"})
    assert cfg["seed"] == 2


def test_resolve_juror_config_per_juror_env_var_takes_priority(monkeypatch):
    monkeypatch.setenv("PSALM_JURY_API_KEY", "sk-jury-wide")
    monkeypatch.setenv("PSALM_JUROR_1_API_KEY", "sk-juror-1")
    cfg0 = resolve_juror_config(0, {})
    cfg1 = resolve_juror_config(1, {})
    assert cfg0["api_key"] == "sk-jury-wide"
    assert cfg1["api_key"] == "sk-juror-1"


def test_resolve_juror_config_falls_back_to_global_env_var(monkeypatch):
    monkeypatch.setenv("PSALM_API_KEY", "sk-global")
    cfg = resolve_juror_config(0, {})
    assert cfg["api_key"] == "sk-global"


def test_resolve_juror_config_raises_when_no_key_available():
    with pytest.raises(ValueError, match="juror 0"):
        resolve_juror_config(0, {})
