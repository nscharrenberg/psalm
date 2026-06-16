import json
from unsloth import FastLanguageModel
from typing import Tuple, Optional

import torch
from huggingface_hub import hf_hub_download
from transformers import PreTrainedTokenizerBase

from psalm.configs.models.model_config import ModelConfig



def _load_base_with_unsloth(model_name: str, cfg: ModelConfig):
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=cfg.max_seq_length,
        dtype=cfg.dtype,
        load_in_4bit=cfg.load_in_4bit,
        load_in_8bit=cfg.load_in_8bit,
        load_in_16bit=cfg.load_in_16bit,
        full_finetuning=False,
        token=cfg.token,
        device_map=cfg.device_map,
        fix_tokenizer=cfg.fix_tokenizer,
        trust_remote_code=cfg.trust_remote_code,
        use_gradient_checkpointing=cfg.use_gradient_checkpointing,
        resize_model_vocab=cfg.resize_model_vocab,
        revision=cfg.revision,
        use_exact_model_name=cfg.use_exact_model_name,
        offload_embedding=cfg.offload_embedding,
        fast_inference=cfg.fast_inference,
        gpu_memory_utilization=cfg.gpu_memory_utilization,
        float8_kv_cache=cfg.float8_kv_cache,
        random_state=cfg.random_state,
        max_lora_rank=cfg.max_lora_rank,
    )
    return model, tokenizer


def load_reference_model(
    cfg: ModelConfig, reference_model_name: str
) -> Tuple[torch.nn.Module, PreTrainedTokenizerBase]:
    """
    Load a frozen reference model.
    - First, try to load directly via Unsloth (works for merged checkpoints).
    - If that fails, assume it's a LoRA adapter repo with adapter_config.json:
      - Read base_model_name_or_path from adapter_config.json
      - Load base via Unsloth
      - Attach adapters via PEFT
    """
    # Try direct load (merged checkpoints or full models)
    try:
        model, tokenizer = _load_base_with_unsloth(reference_model_name, cfg)
        return model.eval(), tokenizer
    except Exception as e_primary:
        # Try LoRA adapter path
        try:
            adapter_cfg_path = hf_hub_download(
                repo_id=reference_model_name, filename="adapter_config.json"
            )
            with open(adapter_cfg_path, "r", encoding="utf-8") as f:
                adapter_cfg = json.load(f)
            base_name = adapter_cfg.get("base_model_name_or_path", None)
            if base_name is None:
                raise RuntimeError(
                    "adapter_config.json missing 'base_model_name_or_path'."
                )

            base_model, tokenizer = _load_base_with_unsloth(base_name, cfg)

            # Attach adapters
            try:
                from peft import PeftModel
            except ImportError as e_peft:
                raise RuntimeError(
                    "peft is required to load LoRA adapters as reference. "
                    "Install with `pip install peft`."
                ) from e_peft

            peft_model = PeftModel.from_pretrained(base_model, reference_model_name)
            return peft_model.eval(), tokenizer

        except Exception as e_adapter:
            raise RuntimeError(
                f"Failed to load reference model '{reference_model_name}'. "
                f"Direct load error: {repr(e_primary)} | "
                f"Adapter load error: {repr(e_adapter)}"
            )