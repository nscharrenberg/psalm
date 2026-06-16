import unsloth  # Must come before transformers/trl for optimal patching
import os

from rich.console import Console
from rich.status import Status
from mlflow.entities import RunStatus

from psalm.configs.npo_run_config import NPORunConfig
from psalm.datasets.collators.npo_data_collator import NPODataCollator
from psalm.datasets.unlearning_dataset import build_unlearning_train_dataset
from psalm.models.huggingface_model import HuggingFaceModel
from psalm.models.chat_templates.unsloth_qa_chat_template import UnslothQAChatTemplate
from psalm.models.reference_loader import load_reference_model
from psalm.trainers.npo_trainer import NPOTrainer
from psalm.trainers.utils.mlflow_utils import (
    mlflow_run_start,
    mlflow_get_run_id,
    mlflow_log_params,
    mlflow_transformer_log_model,
    mlflow_run_end,
)

console = Console()


def main():
    console.rule("Unlearn with NPO")

    cfg = NPORunConfig()
    npo = cfg.npo

    # Make sure column pruning is disabled since we use a custom collator
    cfg.trainer.remove_unused_columns = False

    # Optional: quiet tokenizers fork-parallelism warning
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    # MLflow
    if cfg.mlflow.use_mlflow:
        mlflow_run_start(cfg.mlflow)
        console.print(f"MLFlow Run started with ID: {mlflow_get_run_id()}")

    # Load policy model (trainable)
    policy = HuggingFaceModel(cfg.model, cfg.lora)

    # Apply chat template
    chat_template = UnslothQAChatTemplate(cfg.chat_template, policy)
    policy = chat_template.load()

    # Load frozen reference
    ref_name = npo.reference_model_name or cfg.model.model_name
    ref_model, _ = load_reference_model(cfg.model, ref_name)

    # Build dataset (forget + retain). We assume QA columns 'question'/'answer';
    # extra columns like ti_id/author are preserved.
    dataset_text_field = cfg.trainer.dataset_text_field
    train_dataset = build_unlearning_train_dataset(
        base_dataset_cfg=cfg.dataset,
        forget_split=npo.forget_split,
        retain_split=npo.retain_split,
        chat_template=chat_template,
        dataset_text_field=dataset_text_field,
        question_column="question",
        answer_column="answer",
    )

    # Optional balancing of forget:retain ratio
    if npo.retain_split is not None and npo.forget_retain_ratio != 1.0:
        with Status("Rebalancing forget/retain ratio", spinner="monkey"):
            forget = train_dataset.filter(lambda x: x["is_forget"] == 1)
            retain = train_dataset.filter(lambda x: x["is_forget"] == 0)

            import math

            target_forget = len(forget)
            target_retain = int(
                math.ceil(target_forget / max(npo.forget_retain_ratio, 1e-8))
            )

            if len(retain) > 0 and target_retain > 0:
                retain = retain.shuffle(seed=cfg.trainer.seed).select(
                    range(min(target_retain, len(retain)))
                )
                from datasets import concatenate_datasets

                train_dataset = concatenate_datasets([forget, retain]).shuffle(
                    seed=cfg.trainer.seed
                )

    # Collator constructs masks from chat template markers
    collator = NPODataCollator(
        tokenizer=policy.tokenizer,
        response_part_text=cfg.chat_template.response_part,
        pad_to_multiple_of=cfg.trainer.pad_to_multiple_of,
    )

    # NPO Trainer
    trainer = NPOTrainer(
        model=policy.model,
        args=cfg.trainer,
        train_dataset=train_dataset,
        data_collator=collator,
        tokenizer=policy.tokenizer,  # harmless deprecation warning in HF >= 4.56
        reference_model=ref_model,
        npo_config=npo,
    )

    # if cfg.mlflow.use_mlflow:
    #     mlflow_log_params(cfg.to_dict())

    run_status = RunStatus.RUNNING
    try:
        with Status("Unlearning (NPO)...", spinner="monkey") as status:
            trainer.train(resume_from_checkpoint=cfg.resume_from_checkpoint)
            status.update("Unlearning complete!")

            # Save policy
            save_dir = cfg.trainer.output_dir
            os.makedirs(save_dir, exist_ok=True)
            policy.model.save_pretrained(save_dir)
            policy.tokenizer.save_pretrained(save_dir)

            # Optionally merge LoRA adapters
            if cfg.save.merge_model and hasattr(trainer.model, "merge_and_unload"):
                status.update("Merging LoRA adapters into base...")
                merged_dir = os.path.join(save_dir, "merged")
                os.makedirs(merged_dir, exist_ok=True)
                merged = trainer.model.merge_and_unload()
                merged.save_pretrained(merged_dir)
                policy.tokenizer.save_pretrained(merged_dir)

            if cfg.mlflow.use_mlflow:
                status.update("Logging model to MLflow...")
                mlflow_transformer_log_model(
                    trainer.model, policy.tokenizer, cfg.mlflow.artifact_path
                )
                status.update("MLflow logging complete.")

            run_status = RunStatus.FINISHED
    except Exception:
        console.print_exception()
        run_status = RunStatus.FAILED
    finally:
        if cfg.mlflow.use_mlflow:
            mlflow_run_end(RunStatus.to_string(run_status))


if __name__ == "__main__":
    main()