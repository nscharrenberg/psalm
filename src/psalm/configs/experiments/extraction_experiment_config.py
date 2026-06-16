from dataclasses import dataclass, field
from typing import Optional

from psalm.configs import InferenceConfig, DatasetConfig
from psalm.configs.training.npo_config import NPOConfig
from psalm.configs.utils.save_results import SaveResultsConfig
from psalm.utils.env_utils import get_env_by_name_or_default


@dataclass
class ExtractionExperimentConfig:
    inference_config: InferenceConfig = field(default_factory=lambda: InferenceConfig())
    dataset: DatasetConfig = field(default_factory=lambda: DatasetConfig())
    npo: NPOConfig = field(default_factory=lambda: NPOConfig())
    save: SaveResultsConfig = field(default_factory=lambda: SaveResultsConfig())
    random_sample: bool = field(default_factory=lambda: get_env_by_name_or_default("EXPERIMENTS_RANDOM_SAMPLE", True, bool))
    n_samples: int = field(default_factory=lambda: get_env_by_name_or_default("EXPERIMENTS_N_SAMPLES", 10, int))
    dataset_text_field: Optional[str] = field(
        default_factory=lambda: get_env_by_name_or_default("DATASET_TEXT_FIELD", "text", str))
    random_state: int = field(
        default_factory=lambda: get_env_by_name_or_default("RANDOM_STATE", 3407, int))
