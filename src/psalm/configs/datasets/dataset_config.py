import os
from dataclasses import dataclass, field
from typing import Optional, Union, Sequence, Mapping

from datasets import Split, Features
from dotenv import load_dotenv

from psalm.utils.env_utils import get_env_by_name_or_default, get_dict_env_by_name_or_default

load_dotenv()

@dataclass
class DatasetConfig:
    path: str = field(default_factory=lambda: get_env_by_name_or_default("DATASET_PATH", "nscharrenberg/DBNL-public-qa-english-translation", str))
    subset: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("DATASET_SUBSET", "full", str))
    split: Optional[Union[str, Split, list[str], list[Split]]] = field(default_factory=lambda: get_env_by_name_or_default("DATASET_SPLIT", "train", str))
    data_dir: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("DATASET_DATA_DIR", None, str))
    data_files: Optional[Union[str, Sequence[str], Mapping[str, Union[str, Sequence[str]]]]] = field(default_factory=lambda: get_env_by_name_or_default("DATASET_DATA_FILES", None, str))
    cache_dir: Optional[str] = field(default_factory=lambda: get_env_by_name_or_default("DATASET_CACHE_DIR", None, str))
    features: Optional[Features] = field(default_factory=lambda: get_dict_env_by_name_or_default("DATASET_FEATURES", None))
    num_proc: Optional[int] = field(default_factory=lambda: get_env_by_name_or_default("DATASET_NUM_PROC", None, int))
    streaming: bool = field(default_factory=lambda: get_env_by_name_or_default("DATASET_STREAMING", False, bool))