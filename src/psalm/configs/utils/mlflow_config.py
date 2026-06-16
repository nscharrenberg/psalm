import os
import time
from dataclasses import dataclass, field
from dotenv import load_dotenv
from datetime import datetime

from psalm.utils.env_utils import get_env_by_name_or_default

load_dotenv()


@dataclass
class MLFlowConfig:
    use_mlflow: bool = field(default_factory=lambda: get_env_by_name_or_default("USE_MLFLOW", False, bool))
    tracking_url: str = field(default_factory=lambda: get_env_by_name_or_default("MLFLOW_TRACKING_URL", "http://localhost:5000", str))
    experiment_name: str = field(default_factory=lambda: get_env_by_name_or_default("MLFLOW_EXPERIMENT_NAME", "psalm", str))
    run_name: str = field(default_factory=lambda: get_env_by_name_or_default("RUN_NAME", f"psalm-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}-{int(time.time())}", str))
    artifact_path: str = field(default_factory=lambda: get_env_by_name_or_default("MLFLOW_ARTIFACT_PATH", "psalm", str))
    log_system_metrics: bool = field(default_factory=lambda: get_env_by_name_or_default("MLFLOW_LOG_SYSTEM_METRICS", True, bool))