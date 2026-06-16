from dataclasses import dataclass, field, asdict
from typing import Optional

from dotenv import load_dotenv

from psalm.configs.models.chat_template_config import ChatTemplateConfig
from psalm.configs.datasets.dataset_config import DatasetConfig
from psalm.configs.training.early_stopping_config import EarlyStoppingConfig
from psalm.configs.models.lora_config import LoRAConfig
from psalm.configs.utils.mlflow_config import MLFlowConfig
from psalm.configs.models.model_config import ModelConfig
from psalm.configs.utils.save_config import SaveConfig
from psalm.configs.training.trainer_config import TrainerConfig
from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()

@dataclass
class FinetuneConfig:
    mlflow: MLFlowConfig = field(default_factory=lambda: MLFlowConfig())
    dataset: DatasetConfig = field(default_factory=lambda: DatasetConfig())
    lora: LoRAConfig = field(default_factory=lambda: LoRAConfig())
    model: ModelConfig = field(default_factory=lambda: ModelConfig())
    save: SaveConfig = field(default_factory=lambda: SaveConfig())
    trainer: TrainerConfig = field(default_factory=lambda: TrainerConfig())
    chat_template: ChatTemplateConfig = field(default_factory=lambda: ChatTemplateConfig())
    early_stopping: EarlyStoppingConfig = field(default_factory=lambda: EarlyStoppingConfig())
    resume_from_checkpoint: Optional[str] = field(
        default_factory=lambda: get_env_by_name_or_default("RESUME_FROM_CHECKPOINT", None, str))

    def to_dict(self):
        output_dict = {}

        # Convert each dataclass to dictionary and add namespace prefix to avoid key conflicts
        configs = {
            'mlflow': asdict(self.mlflow),
            'dataset': asdict(self.dataset),
            'lora': asdict(self.lora),
            'model': asdict(self.model),
            'save': asdict(self.save),
            'trainer': asdict(self.trainer),
            'chat_template': asdict(self.chat_template),
            'early_stopping': asdict(self.early_stopping)
        }

        # Flatten the dictionary by adding each key-value pair
        for namespace, config_dict in configs.items():
            for key, value in config_dict.items():
                output_dict[f"{key}"] = value
    
        return output_dict