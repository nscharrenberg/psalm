import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()

@dataclass
class SaveResultsConfig:
    save_to: str = field(default_factory=lambda: get_env_by_name_or_default("EXTRACTION_SAVE_TO", "results/extraction/results.parquet", str))
