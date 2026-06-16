from dataclasses import dataclass, field
from typing import Optional

from psalm.utils.env_utils import get_env_by_name_or_default


@dataclass
class EvaluationExperimentConfig:
    evaluation_gpt_model: str = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_GPT_MODEL", "gpt-5-mini", str))
    dataset_path: str = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_DATASET_PATH", "results.json", str))
    save_dir: str = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_SAVE_DIR", None, str))
    max_retries: int = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_MAX_RETRIES", 3, int))
    max_concurrent: int = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_MAX_CONCURRENCY", 15, int))
    save_intermediate: bool = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_SAVE_INTERMEDIATE", True, bool))
    checkpoint_frequency: int = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_CHECKPOINT_FREQUENCY", 1, int))
    shuffle: bool = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_SHUFFLE", True, bool))
    seed: Optional[int] = field(default_factory=lambda: get_env_by_name_or_default("EVALUATION_EXPERIMENT_RANDOM_STATE", 42, int))
