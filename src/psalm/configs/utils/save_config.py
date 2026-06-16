import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()

@dataclass
class SaveConfig:
    # Merge model
    merge_model: bool = field(default_factory=lambda: get_env_by_name_or_default("MERGE_MODEL", False, bool))
    merge_method: str = field(default_factory=lambda: get_env_by_name_or_default("MERGE_METHOD", "merged_16bit", str))

    save_gguf: bool = field(default_factory=lambda: get_env_by_name_or_default("SAVE_GGUF", False, bool))
    gguf_quantization_method: str = field(default_factory=lambda: get_env_by_name_or_default("GGUF_QUANTIZATION_METHOD", "fp16", str))