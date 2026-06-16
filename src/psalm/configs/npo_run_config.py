from dataclasses import dataclass, field, asdict
from typing import Optional

from dotenv import load_dotenv

from psalm.configs.datasets.dataset_config import DatasetConfig
from psalm.configs.models.chat_template_config import ChatTemplateConfig
from psalm.configs.models.lora_config import LoRAConfig
from psalm.configs.models.model_config import ModelConfig
from psalm.configs.training.trainer_config import TrainerConfig
from psalm.configs.utils.mlflow_config import MLFlowConfig
from psalm.configs.utils.save_config import SaveConfig
from psalm.configs.training.npo_config import NPOConfig
from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()


@dataclass
class NPORunConfig:
    mlflow: MLFlowConfig = field(default_factory=lambda: MLFlowConfig())
    dataset: DatasetConfig = field(default_factory=lambda: DatasetConfig())
    lora: LoRAConfig = field(default_factory=lambda: LoRAConfig())
    model: ModelConfig = field(default_factory=lambda: ModelConfig())
    save: SaveConfig = field(default_factory=lambda: SaveConfig())
    trainer: TrainerConfig = field(default_factory=lambda: TrainerConfig())
    chat_template: ChatTemplateConfig = field(default_factory=lambda: ChatTemplateConfig())
    npo: NPOConfig = field(default_factory=lambda: NPOConfig())

    resume_from_checkpoint: Optional[str] = field(
        default_factory=lambda: get_env_by_name_or_default("RESUME_FROM_CHECKPOINT", None, str)
    )

    def to_dict(self) -> dict:
        out: dict = {}
        packs = {
            "mlflow": asdict(self.mlflow),
            "dataset": asdict(self.dataset),
            "lora": asdict(self.lora),
            "model": asdict(self.model),
            "save": asdict(self.save),
            "trainer": asdict(self.trainer),
            "chat_template": asdict(self.chat_template),
            "npo": asdict(self.npo),
        }
        for _, d in packs.items():
            for k, v in d.items():
                out[k] = v
        return out