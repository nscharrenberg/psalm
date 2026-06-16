import gradio as gr

from psalm.ui.demo.components.shared import (
    create_panel_title,
    create_submit_button,
    create_text_input,
)
from psalm.ui.demo.state import CopyrightText, DemoState


def create_copyright_text_form(
    state: gr.State,
    tabs: gr.Tabs,
) -> None:
    with gr.Group():
        create_panel_title(
            "Source text",
            (
                "Paste the text you want to compare against. "
                "This may be an excerpt from a book or another protected source."
            ),
        )

        with gr.Row():
            title_input = create_text_input(
                "Source title",
                placeholder="Optional",
            )
            author_input = create_text_input(
                "Source author",
                placeholder="Optional",
            )

        text_input = create_text_input(
            "Source text",
            placeholder="Paste the source text here",
            lines=14,
            info="Required",
        )

        save_btn = create_submit_button(
            "Save source text",
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
            gr.Warning("Please provide the source text.")
            return current_state, "Source text has not been saved."

        current_state.copyright_text = CopyrightText(
            title=title_value.strip(),
            author=author_value.strip(),
            text=text_value.strip(),
        )
        current_state.reset_analysis()

        return current_state, "Source text saved."

    save_btn.click(
        fn=handle_submit,
        inputs=[state, title_input, author_input, text_input],
        outputs=[state, save_status],
    )