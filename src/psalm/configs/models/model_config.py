import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()

@dataclass
class ModelConfig:
    model_name: str = field(default_factory=lambda: get_env_by_name_or_default("MODEL_NAME", "unsloth/Llama-3.2-1B-Instruct", str))
    max_seq_length: int = field(default_factory=lambda: get_env_by_name_or_default("MAX_SEQ_LENGTH", 2048, int))
    dtype: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("DTYPE", None, str))
    load_in_4bit: bool = field(default_factory=lambda: get_env_by_name_or_default("LOAD_IN_4BIT", False, bool))
    load_in_8bit: bool = field(default_factory=lambda: get_env_by_name_or_default("LOAD_IN_8BIT", False, bool))
    load_in_16bit: bool = field(default_factory=lambda: get_env_by_name_or_default("LOAD_IN_16BIT", False, bool))
    full_finetuning: bool = field(default_factory=lambda: get_env_by_name_or_default("FULL_FINETUNING", False, bool))
    token: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("TOKEN", None, str))
    device_map: str = field(default_factory=lambda: get_env_by_name_or_default("DEVICE_MAP", "sequential", str))
    fix_tokenizer: bool = field(default_factory=lambda: get_env_by_name_or_default("FIX_TOKENIZER", True, bool))
    trust_remote_code: bool = field(default_factory=lambda: get_env_by_name_or_default("TRUST_REMOTE_CODE", False, bool))
    use_gradient_checkpointing: str = field(default_factory=lambda: get_env_by_name_or_default("GRADIENT_CHECKPOINTING", "unsloth", str))
    resize_model_vocab: Optional[int] = field(default_factory=lambda: get_env_by_name_or_default("RESIZE_MODEL_VOCAB", None, int))
    revision: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("REVISION", None, str))
    use_exact_model_name: bool = field(default_factory=lambda: get_env_by_name_or_default("USE_EXACT_MODEL_NAME", False, bool))
    offload_embedding: bool = field(default_factory=lambda: get_env_by_name_or_default("OFFLOAD_EMBEDDING", False, bool))
    fast_inference: bool = field(default_factory=lambda: get_env_by_name_or_default("FAST_INFERENCE", False, bool))
    gpu_memory_utilization: float = field(default_factory=lambda: get_env_by_name_or_default("GPU_MEMORY_UTILIZATION", 0.5, float))
    float8_kv_cache: bool = field(default_factory=lambda: get_env_by_name_or_default("FLOAT8_KV_CACHE", False, bool))
    random_state: int = field(default_factory=lambda: get_env_by_name_or_default("RANDOM_STATE", 3407, int))
    max_lora_rank: int = field(default_factory=lambda: get_env_by_name_or_default("MAX_LORA_RANK", 64, int))