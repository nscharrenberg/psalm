import ast
import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

from psalm.utils.env_utils import get_dict_env_by_name_or_default, get_env_by_name_or_default

load_dotenv()

@dataclass
class ChatTemplateConfig:
    chat_template: str = field(default_factory=lambda: get_env_by_name_or_default("CHAT_TEMPLATE", "llama", str))
    mapping: dict = field(default_factory=lambda: get_dict_env_by_name_or_default("CHAT_TEMPLATE_MAPPING", {"role" : "role", "content": "content", "user" : "user", "assistant" : "assistant"}))
    map_eos_token: bool = field(default_factory=lambda: get_env_by_name_or_default("MAP_EOS_TOKEN", True, bool))
    system_message: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("SYSTEM_MESSAGE", None, str))
    train_on_responses_only: bool = field(default_factory=lambda: get_env_by_name_or_default("TRAIN_ON_RESPONSES_ONLY", False, bool))
    instruction_part: str = field(default_factory=lambda: get_env_by_name_or_default("INSTRUCTION_PART", "<|start_header_id|>user<|end_header_id|>\n\n", str))
    response_part: str = field(default_factory=lambda: get_env_by_name_or_default("RESPONSE_PART", "<|start_header_id|>assistant<|end_header_id|>\n\n", str))
