import gradio as gr

from psalm.ui.demo.components.shared import (
    create_panel_title,
    create_submit_button,
    create_text_input,
)
from psalm.ui.demo.state import DemoState, TargetText


def create_target_text_form(
    state: gr.State,
    tabs: gr.Tabs,
) -> None:
    with gr.Group():
        create_panel_title(
            "Draft text",
            (
                "Paste the text you want to review. "
                "This is the draft that will be compared to the source."
            ),
        )

        with gr.Row():
            title_input = create_text_input(
                "Draft title",
                placeholder="Optional",
            )
            author_input = create_text_input(
                "Draft author",
                placeholder="Optional",
            )

        text_input = create_text_input(
            "Draft text",
            placeholder="Paste the draft text here",
            lines=14,
            info="Required",
        )

        save_btn = create_submit_button(
            "Save draft text",
            variant="secondary",
        )

        save_status = gr.Markdown("")

    def handle_submit(
        current_state: DemoState,
        title_value: str,
        author_value: str,
        text_value: str,
    ):
        if not text_value or not text_value.strip():
            gr.Warning("Please provide the draft text.")
            return current_state, "Draft text has not been saved."

        current_state.target_text = TargetText(
            title=title_value.strip(),
            author=author_value.strip(),
            text=text_value.strip(),
        )
        current_state.reset_analysis()

        return current_state, "Draft text saved."

    save_btn.click(
        fn=handle_submit,
        inputs=[state, title_input, author_input, text_input],
        outputs=[state, save_status],
    )