import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from psalm.utils.env_utils import get_env_by_name_or_default, get_list_env_by_name_or_default

load_dotenv()

@dataclass
class LoRAConfig:
    use_lora: bool = field(default_factory=lambda: get_env_by_name_or_default("USE_LORA", True, bool))
    rank: int = field(default_factory=lambda: get_env_by_name_or_default("LORA_RANK", 4, int))
    alpha: int = field(default_factory=lambda: get_env_by_name_or_default("LORA_ALPHA", 16, int))
    dropout: float = field(default_factory=lambda: get_env_by_name_or_default("LORA_DROPOUT", 0.1, float))
    target_modules: list[str] = field(default_factory=lambda: get_list_env_by_name_or_default("LORA_TARGET_MODULES", "q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj".split(",")))
    bias: str = field(default_factory=lambda: get_env_by_name_or_default("LORA_BIAS", "none", str))
    use_gradient_checkpointing: str = field(default_factory=lambda: get_env_by_name_or_default("LORA_USE_GRADIENT_CHECKPOINTING", "unsloth", str))
    random_state: int = field(default_factory=lambda: get_env_by_name_or_default("LORA_RANDOM_STATE", 3407, int))
    use_rslora: bool = field(default_factory=lambda: get_env_by_name_or_default("LORA_USE_RSLORA", False, bool))

