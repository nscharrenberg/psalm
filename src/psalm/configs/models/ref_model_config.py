import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

from psalm.configs import ModelConfig
from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()

@dataclass
class RefModelConfig(ModelConfig):
    model_name: str = field(default_factory=lambda: get_env_by_name_or_default("REF_MODEL_NAME", "unsloth/Llama-3.2-1B-Instruct", str))
    load_adapters: bool = field(
        default_factory=lambda: get_env_by_name_or_default("REF_MODEL_LOAD_ADAPTERS", True, bool))
    merge_adapters: bool = field(
        default_factory=lambda: get_env_by_name_or_default("REF_MODEL_MERGE_ADAPTERS", True, bool))