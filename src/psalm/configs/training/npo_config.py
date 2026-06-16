from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()


@dataclass
class NPOConfig:
    # Splits
    forget_split: str = field(
        default_factory=lambda: get_env_by_name_or_default(
            "FORGET_SPLIT", "forget", str
        )
    )
    retain_split: Optional[str] = field(
        default_factory=lambda: get_env_by_name_or_default(
            "RETAIN_SPLIT", "retain", str
        )
    )

    # NPO hyperparameters
    beta: float = field(
        default_factory=lambda: get_env_by_name_or_default("NPO_BETA", 0.1, float)
    )
    length_normalize: bool = field(
        default_factory=lambda: get_env_by_name_or_default(
            "NPO_LENGTH_NORMALIZE", True, bool
        )
    )
    clamp_adv_abs: Optional[float] = field(
        default_factory=lambda: get_env_by_name_or_default(
            "NPO_CLAMP_ADV_ABS", None, float
        )
    )

    # Retain objective to preserve utility on retain split.
    # Options: "none", "sft_ce", "kl"
    retain_objective: str = field(
        default_factory=lambda: get_env_by_name_or_default(
            "NPO_RETAIN_OBJECTIVE", "sft_ce", str
        )
    )
    retain_weight: float = field(
        default_factory=lambda: get_env_by_name_or_default(
            "NPO_RETAIN_WEIGHT", 1.0, float
        )
    )

    # Frozen reference model (for NPO).
    # If your reference is a LoRA adapter repo on HF (e.g., "org/model-lora"),
    # set NPO_REFERENCE_MODEL to it; we'll attempt to load the base defined in the
    # adapter_config.json and attach adapters. Otherwise, point to a merged checkpoint.
    # If None, defaults to current policy model_name.
    reference_model_name: Optional[str] = field(
        default_factory=lambda: get_env_by_name_or_default(
            "NPO_REFERENCE_MODEL", None, str
        )
    )

    # Optional rebalancing: approximate forget:retain ratio in the training set.
    forget_retain_ratio: float = field(
        default_factory=lambda: get_env_by_name_or_default(
            "NPO_FORGET_RETAIN_RATIO", 1.0, float
        )
    )