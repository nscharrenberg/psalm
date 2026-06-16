from dataclasses import dataclass, field

from psalm.utils.env_utils import get_env_by_name_or_default
from sdg.configs.model_config import ModelConfig


@dataclass
class ControlExperimentConfig:
    model: ModelConfig = field(default_factory=lambda: ModelConfig())
    dataset_path: str = field(default_factory=lambda: get_env_by_name_or_default("CONTROL_EXPERIMENT_DATASET_PATH", "control.json", str))
    save_dir: str = field(default_factory=lambda: get_env_by_name_or_default("CONTROL_EXPERIMENT_SAVE_DIR", None, str))
    max_retries: int = field(default_factory=lambda: get_env_by_name_or_default("CONTROL_EXPERIMENT_MAX_RETRIES", 3, int))
    debug: bool = field(default_factory=lambda: get_env_by_name_or_default("CONTROL_EXPERIMENT_DEBUG", False, bool))