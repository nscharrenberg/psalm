import typing
from typing import Optional
import unsloth
import torch
from rich.console import Console
from rich.status import Status
from torch import nn
from transformers import PreTrainedTokenizerBase, StoppingCriteria, StoppingCriteriaList
from unsloth import FastLanguageModel

from psalm.configs import ModelConfig, LoRAConfig, InferenceConfig

if typing.TYPE_CHECKING:
    from psalm.models.chat_templates.unsloth_chat_template import UnslothChatTemplate

console = Console()

class HuggingFaceModel:
    def __init__(self, model_config: ModelConfig, lora_config: Optional[LoRAConfig] = None):
        self._model_config = model_config
        self._lora_config = lora_config
        self.model: Optional[torch.nn.Module] = None
        self.tokenizer: Optional[PreTrainedTokenizerBase] = None

        self.load()

    def load(self):
        """
        Loads the model and tokenizer, applying additional configurations if necessary.

        This method retrieves the model and tokenizer from HuggingFace. If specific
        conditions are met, it loads Low-Rank Adaptation (LoRA) weights to the model.

        Returns:
            Tuple[Model, Tokenizer]: A tuple containing the model and its associated tokenizer.
        """
        with Status("Loading model (and tokenizer) from HuggingFace", spinner="monkey") as status:
            self.model, self.tokenizer = self._load_model()

            if self._use_lora():
                status.update("Loading LoRA weights")
                self.model = self._load_peft()

            return self.model, self.tokenizer

    def _load_peft(self) -> nn.Module:
        """
        Loads the PEFT (Parameter-Efficient Fine-Tuning) model based on the configuration provided.

        The method first checks if the base model is loaded. If not, it raises an exception.
        If the configured LoRA (Low-Rank Adaptation) is enabled, it returns the PEFT-enhanced
        model configured with the parameters from the `self._lora_config`. Otherwise, it
        returns the original model.

        Raises:
            ValueError: If the model (`self._model`) is not loaded when the method is called.

        Returns:
            nn.Module: The PEFT-enhanced model or the original model, depending on the
            configuration.
        """
        if self.model is None:
            raise ValueError("Model is not loaded yet.")

        if self._use_lora():
            return FastLanguageModel.get_peft_model(
                self.model,
                r=self._lora_config.rank,
                lora_alpha=self._lora_config.alpha,
                lora_dropout=self._lora_config.dropout,
                bias=self._lora_config.bias,
                target_modules=self._lora_config.target_modules,
                use_gradient_checkpointing=self._lora_config.use_gradient_checkpointing,
                random_state=self._lora_config.random_state,
                use_rslora=self._lora_config.use_rslora
            )
        else:
            return self.model

    def _load_model(self) -> tuple[torch.nn.Module, PreTrainedTokenizerBase]:
        """
        Loads a pre-trained language model and its associated tokenizer.

        This function leverages the FastLanguageModel library to load a pre-trained
        language model specified by the `self._model_config` attributes. The function
        configures the model and tokenizer based on multiple parameters provided in
        the model configuration. Returns the loaded model and tokenizer.

        Returns:
            tuple[torch.nn.Module, PreTrainedTokenizerBase]: A tuple containing the
            loaded language model and its tokenizer.
        """
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=self._model_config.model_name,
            max_seq_length=self._model_config.max_seq_length,
            dtype=self._model_config.dtype,
            load_in_4bit=self._model_config.load_in_4bit,
            load_in_8bit=self._model_config.load_in_8bit,
            load_in_16bit=self._model_config.load_in_16bit,
            full_finetuning=self._model_config.full_finetuning,
            token=self._model_config.token,
            device_map=self._model_config.device_map,
            fix_tokenizer=self._model_config.fix_tokenizer,
            trust_remote_code=self._model_config.trust_remote_code,
            use_gradient_checkpointing=self._model_config.use_gradient_checkpointing,
            resize_model_vocab=self._model_config.resize_model_vocab,
            revision=self._model_config.revision,
            use_exact_model_name=self._model_config.use_exact_model_name,
            offload_embedding=self._model_config.offload_embedding,
            fast_inference=self._model_config.fast_inference,
            gpu_memory_utilization=self._model_config.gpu_memory_utilization,
            float8_kv_cache=self._model_config.float8_kv_cache,
            random_state=self._model_config.random_state,
            max_lora_rank=self._model_config.max_lora_rank
        )

        return model, tokenizer

    def inference(self, messages: list[dict[str, str]], chat_template: "UnslothChatTemplate",
                  inference_config: InferenceConfig) -> list[dict[str, str]]:
        if self.tokenizer is None:
            raise ValueError("Tokenizer is not loaded yet.")

        rendered = chat_template.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Tokenize with truncation to ensure we don't exceed max length
        batch = self.tokenizer(
            [rendered],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self._model_config.max_seq_length - inference_config.max_new_tokens  # Leave room for generation
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        batch = {k: v.to(device) for k, v in batch.items()}

        # Enable inference mode
        unsloth.FastLanguageModel.for_inference(self.model)

        class StopOnEOT(StoppingCriteria):
            def __init__(self, eot_id: int):
                self.eot_id = eot_id

            def __call__(self, input_ids, scores, **kwargs) -> bool:
                return input_ids[0, -1].item() == self.eot_id

        eot_id = self.tokenizer.convert_tokens_to_ids("<|eot_id|>")
        stoppers = StoppingCriteriaList([StopOnEOT(eot_id)])

        cfg = inference_config

        gen = self.model.generate(
            input_ids=batch["input_ids"],
            attention_mask=batch["attention_mask"],
            max_new_tokens=cfg.max_new_tokens,
            do_sample=cfg.do_sample,
            temperature=cfg.temperature if cfg.do_sample else 1.0,  # Temperature only matters when sampling
            top_p=cfg.top_p,
            top_k=cfg.top_k,
            repetition_penalty=cfg.repetition_penalty,
            eos_token_id=self.tokenizer.eos_token_id,
            pad_token_id=self.tokenizer.eos_token_id,
            use_cache=cfg.use_cache,
            stopping_criteria=stoppers,
        )

        prompt_len = batch["input_ids"].shape[1]
        generated_only = gen[0][prompt_len:]
        answer = self.tokenizer.decode(generated_only, skip_special_tokens=True).strip()

        messages.append({"role": "assistant", "content": answer})

        return messages

    def _use_lora(self):
        """
        Checks if the LoRA (Low-Rank Adaptation) configuration is enabled and in use.

        This method evaluates whether the system is configured to utilize the Low-Rank
        Adaptation mechanism by checking the presence and activation status of
        the LoRA configuration.

        Returns:
            bool: True if the LoRA configuration is present and set to use LoRA,
            otherwise False.
        """
        return self._lora_config is not None and self._lora_config.use_lora

    @staticmethod
    def load_and_merge_adapters(model_path: str, model_config: ModelConfig) -> tuple[
        torch.nn.Module, PreTrainedTokenizerBase]:
        """
        Load a model with LoRA adapters and merge them into the base model.

        Args:
            model_path: Path to the model with adapters
            model_config: Model configuration

        Returns:
            Merged model and tokenizer
        """
        from unsloth import FastLanguageModel

        with Status("Loading model with adapters and merging...", spinner="monkey"):
            # Load model with adapters
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_path,
                max_seq_length=model_config.max_seq_length,
                dtype=model_config.dtype,
                load_in_4bit=model_config.load_in_4bit,
                load_in_8bit=model_config.load_in_8bit,
                load_in_16bit=model_config.load_in_16bit,
                token=model_config.token,
                device_map=model_config.device_map,
                trust_remote_code=model_config.trust_remote_code,
                revision=model_config.revision,
            )

            # Check if model has adapters and merge them
            if hasattr(model, 'merge_and_unload'):
                console.print("[yellow]Merging LoRA adapters into reference model...[/yellow]")
                model = model.merge_and_unload()

            return model, tokenizer