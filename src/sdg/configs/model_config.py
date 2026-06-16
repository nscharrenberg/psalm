from dataclasses import dataclass, field
from typing import Optional

from psalm.utils.env_utils import get_env_by_name_or_default, get_dict_env_by_name_or_default


@dataclass
class ModelConfig:
    model_name: str = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_NAME", "gpt-4o-mini", str))
    temperature: float = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_TEMPERATURE", 0.7))
    seed: Optional[int] = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_SEED", None, int))
    top_p: Optional[float] = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_TOP_P", None, float))
    max_tokens: Optional[int] = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_MAX_TOKENS", None, int))
    reasoning_effort: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_REASONING_EFFORT", None, str))
    timeout: Optional[float] = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_TIMEOUT", 120, float))
    max_retries: Optional[int] = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_MAX_RETRIES", 3, int))
    base_url: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_BASE_URL", None, str))
    organization: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("SDG_MODEL_ORGANIZATION", None, str))
    include_usage: bool = field(default_factory=lambda: get_env_by_name_or_default("SDG_INCLUDE_USAGE", False, bool))

