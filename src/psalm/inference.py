import argparse

from rich.console import Console
from dotenv import load_dotenv

load_dotenv()
console = Console()

from psalm.models.chat_templates.unsloth_qa_chat_template import UnslothQAChatTemplate
from psalm.models import HuggingFaceModel
from psalm.configs import InferenceConfig

def main():
    parser = argparse.ArgumentParser(
        prog="finetune",
        description="Finetuning utility",
    )
    parser.add_argument(
        "--question",
        type=str,
        required=True,
        help="Question prompt to use (e.g., 'what is the capital of france?')",
    )

    args = parser.parse_args()

    question = args.question

    if question is None:
        console.print("Please provide a question prompt.")
        return

    console.rule("Inference PSALM Model")
    cfg = InferenceConfig()

    hf_model_instance = HuggingFaceModel(cfg.model, cfg.lora)
    chat_template_instance = UnslothQAChatTemplate(cfg.chat_template, hf_model_instance)
    hf_model_instance = chat_template_instance.load()

    response = hf_model_instance.inference([
        {"role": "user", "content": question}
    ], chat_template_instance, cfg)

    console.print(response)

if __name__ == "__main__":
    main()