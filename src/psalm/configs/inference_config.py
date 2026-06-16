from dataclasses import dataclass, field

from psalm.configs.models.chat_template_config import ChatTemplateConfig
from psalm.configs.models.lora_config import LoRAConfig
from psalm.configs.models.model_config import ModelConfig
from psalm.utils.env_utils import get_env_by_name_or_default


@dataclass
class InferenceConfig:
    model: ModelConfig = field(default_factory=lambda: ModelConfig())
    # We disable lora for inference
    lora: LoRAConfig = field(default_factory=lambda: LoRAConfig(use_lora=False))
    chat_template: ChatTemplateConfig = field(default_factory=lambda: ChatTemplateConfig())
    max_new_tokens: int = field(default_factory=lambda: get_env_by_name_or_default("MAX_NEW_TOKENS", 1024, int))
    do_sample: bool = field(default_factory=lambda: get_env_by_name_or_default("DO_SAMPLE", True, bool))
    temperature: float = field(default_factory=lambda: get_env_by_name_or_default("TEMPERATURE", 0.1, float))
    top_p: float = field(default_factory=lambda: get_env_by_name_or_default("TOP_P", 1.0, float))
    top_k: int = field(default_factory=lambda: get_env_by_name_or_default("TOP_K", 2, int))
    repetition_penalty: float = field(default_factory=lambda: get_env_by_name_or_default("REPETITION_PENALTY", 1.1, float))
    length_penalty: float = field(default_factory=lambda: get_env_by_name_or_default("LENGTH_PENALTY", 1.0, float))
    num_beams: int = field(default_factory=lambda: get_env_by_name_or_default("NUM_BEAMS", 1, int))
    use_cache: bool = field(default_factory=lambda: get_env_by_name_or_default("USE_CACHE", True, bool))