import gradio as gr

from psalm.ui.demo.app import build_demo


def main() -> None:
    """Entry point for the demo application."""
    demo = build_demo()
    demo.launch(theme=gr.Theme.from_hub("harsh8001/skymist"))


if __name__ == "__main__":
    main()