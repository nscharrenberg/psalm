import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()

@dataclass
class EarlyStoppingConfig:
    use_early_stopping: bool = field(default_factory=lambda: get_env_by_name_or_default("USE_EARLY_STOPPING", False, bool))
    patience: int = field(default_factory=lambda: get_env_by_name_or_default("EARLY_STOPPING_PATIENCE", 3, int))
    stopping_threshold: float = field(default_factory=lambda: get_env_by_name_or_default("EARLY_STOPPING_THRESHOLD", 0.0, float))