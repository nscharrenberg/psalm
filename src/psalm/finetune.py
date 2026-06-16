import unsloth
import os

from mlflow.entities import RunStatus
from rich.status import Status
from transformers import DataCollatorForSeq2Seq
from trl import SFTTrainer

from psalm.configs.finetune_config import FinetuneConfig
from psalm.datasets import HuggingFaceDataset
from rich.console import Console

from psalm.models import HuggingFaceModel
from psalm.models.chat_templates.unsloth_qa_chat_template import UnslothQAChatTemplate
from psalm.trainers.utils.mlflow_utils import mlflow_run_start, mlflow_get_run_id, mlflow_log_params, \
    mlflow_transformer_log_model, mlflow_run_end

console = Console()

def main():
    console.rule("Finetune PSALM Model")

    # Load Config
    cfg = FinetuneConfig()

    if cfg.mlflow.use_mlflow:
        # Start MLFlow Run
        mlflow_run_start(cfg.mlflow)
        console.print(f"MLFlow Run started with ID: {mlflow_get_run_id()}")

    # Instantiate Instances
    hf_model_instance = HuggingFaceModel(cfg.model, cfg.lora)

    hf_dataset_instance = HuggingFaceDataset(cfg.dataset)
    chat_template_instance = UnslothQAChatTemplate(cfg.chat_template, hf_model_instance)

    dataset_text_field = cfg.trainer.dataset_text_field

    # Apply Chat Template to Model
    hf_model_instance = chat_template_instance.load()

    # Apply Chat Template to Dataset
    hf_dataset_instance.format(chat_template_instance, tokenize=False, add_generation_prompt=False, return_column=dataset_text_field)

    trainer_config = cfg.trainer

    trainer = SFTTrainer(
        model=hf_model_instance.model,
        train_dataset=hf_dataset_instance.dataset,
        data_collator=DataCollatorForSeq2Seq(hf_model_instance.tokenizer, model=hf_model_instance.model),
        args=trainer_config,
        processing_class=hf_model_instance.tokenizer
    )

    if cfg.chat_template.train_on_responses_only:
        trainer = unsloth.chat_templates.train_on_responses_only(
            trainer,
            instruction_part=cfg.chat_template.instruction_part,
            response_part=cfg.chat_template.response_part
        )

    if cfg.mlflow.use_mlflow:
        mlflow_log_params(cfg.to_dict())
    run_status = RunStatus.RUNNING
    try:
        with Status("Finetuning...", spinner="monkey") as status:
            trainer.train(resume_from_checkpoint=cfg.resume_from_checkpoint)

            status.update("Finetuning complete!")

            save_config = cfg.save

            if save_config.merge_model:
                status.update("Merging model...")
                try:
                    merged_dir = os.path.join(trainer_config.output_dir, "merged")
                    os.makedirs(merged_dir, exist_ok=True)

                    merged_model = trainer.model.merge_and_unload()
                    merged_model.save_pretrained(merged_dir)

                    hf_model_instance.tokenizer.save_pretrained(merged_dir)

                    if trainer_config.push_to_hub:
                        status.update("Pushing to hub...")
                        merged_repo = trainer_config.hub_model_id + "-merged"
                        merged_model.push_to_hub(merged_repo)
                        hf_model_instance.tokenizer.push_to_hub(merged_repo)

                    status.update(f"Merged model saved to {merged_dir}.")
                except Exception:
                    console.print_exception()

            if cfg.mlflow.use_mlflow:
                status.update("Logging model to MLFlow...")
                mlflow_transformer_log_model(
                    trainer.model,
                    hf_model_instance.tokenizer,
                    cfg.mlflow.artifact_path
                )

                status.update("MLFlow run complete!")

            run_status = RunStatus.FINISHED
    except Exception:
        console.print_exception()
        run_status = RunStatus.FAILED
    finally:
        if cfg.mlflow.use_mlflow:
            mlflow_run_end(RunStatus.to_string(run_status))

if __name__ == "__main__":
    main()