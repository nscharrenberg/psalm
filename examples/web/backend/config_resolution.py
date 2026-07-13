from __future__ import annotations

import os

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TEMPERATURE = 0.1


def resolve_value(posted: str | None, *env_names: str, default: str = "") -> str:
    if posted:
        return posted
    for name in env_names:
        value = os.getenv(name, "")
        if value:
            return value
    return default


def resolve_agent_config(role_prefix: str, posted: dict) -> dict:
    api_key = resolve_value(
        posted.get("api_key"), f"PSALM_{role_prefix}_API_KEY", "PSALM_API_KEY",
    )
    if not api_key:
        raise ValueError(
            f"No API key provided for {role_prefix} and no "
            f"PSALM_{role_prefix}_API_KEY or PSALM_API_KEY environment variable is set."
        )
    return {
        "base_url": resolve_value(
            posted.get("base_url"), f"PSALM_{role_prefix}_BASE_URL", "PSALM_BASE_URL",
            default=_DEFAULT_BASE_URL,
        ),
        "api_key": api_key,
        "model": resolve_value(
            posted.get("model"), f"PSALM_{role_prefix}_MODEL", "PSALM_MODEL",
            default=_DEFAULT_MODEL,
        ),
        "temperature": float(resolve_value(
            posted.get("temperature") and str(posted["temperature"]),
            f"PSALM_{role_prefix}_TEMPERATURE", "PSALM_TEMPERATURE",
            default=str(_DEFAULT_TEMPERATURE),
        )),
    }


def resolve_juror_config(index: int, posted: dict) -> dict:
    juror_prefix = f"PSALM_JUROR_{index}"
    api_key = resolve_value(
        posted.get("api_key"), f"{juror_prefix}_API_KEY", "PSALM_JURY_API_KEY", "PSALM_API_KEY",
    )
    if not api_key:
        raise ValueError(
            f"No API key provided for juror {index} and no "
            f"{juror_prefix}_API_KEY, PSALM_JURY_API_KEY, or PSALM_API_KEY "
            f"environment variable is set."
        )
    seed = posted.get("seed")
    return {
        "base_url": resolve_value(
            posted.get("base_url"), f"{juror_prefix}_BASE_URL", "PSALM_JURY_BASE_URL", "PSALM_BASE_URL",
            default=_DEFAULT_BASE_URL,
        ),
        "api_key": api_key,
        "model": resolve_value(
            posted.get("model"), f"{juror_prefix}_MODEL", "PSALM_JURY_MODEL", "PSALM_MODEL",
            default=_DEFAULT_MODEL,
        ),
        "temperature": float(resolve_value(
            posted.get("temperature") and str(posted["temperature"]),
            f"{juror_prefix}_TEMPERATURE", "PSALM_JURY_TEMPERATURE", "PSALM_TEMPERATURE",
            default=str(_DEFAULT_TEMPERATURE),
        )),
        "seed": seed if seed is not None else index,
    }
