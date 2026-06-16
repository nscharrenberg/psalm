import gradio as gr

from psalm.ui.demo.pages.analysis import create_analysis
from psalm.ui.demo.pages.configure_parameters_form import (
    create_configure_parameters_form,
)
from psalm.ui.demo.pages.copyright_text_form import (
    create_copyright_text_form,
)
from psalm.ui.demo.pages.example_selection_form import (
    create_example_selection_form,
)
from psalm.ui.demo.pages.overview import create_overview
from psalm.ui.demo.pages.select_evaluators_form import (
    create_select_evaluators_form,
)
from psalm.ui.demo.pages.target_text_form import create_target_text_form
from psalm.ui.demo.state import DemoState


def build_demo() -> gr.Blocks:
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate",
        radius_size=gr.themes.sizes.radius_lg,
        text_size=gr.themes.sizes.text_md,
    )

    with gr.Blocks(
        title="PSALM Copyright Review Assistant",
        fill_width=True,
    ) as demo:
        state = gr.State(value=DemoState())

        gr.Markdown(
            """
# PSALM Copyright Review Assistant

A guided workflow for checking whether a draft may be too similar to a source text.

This tool is intended for:
- copywriters
- editors
- content reviewers
- researchers and analysts

It helps with editorial review and triage. It does not provide legal advice.
"""
        )

        with gr.Row():
            with gr.Column(scale=2):
                step_indicator = gr.Markdown()
            with gr.Column(scale=1):
                session_status = gr.Markdown()

        with gr.Tabs(selected="texts") as main_tabs:
            with gr.Tab("1. Texts", id="texts"):
                with gr.Row():
                    with gr.Column(scale=1):
                        create_example_selection_form(state, main_tabs)
                    with gr.Column(scale=2):
                        with gr.Group():
                            gr.Markdown(
                                """
## Add your own texts

If you do not want to use a prepared example, paste your own draft and source text here.
"""
                            )
                            with gr.Row():
                                with gr.Column():
                                    create_target_text_form(state, main_tabs)
                                with gr.Column():
                                    create_copyright_text_form(
                                        state, main_tabs
                                    )

                        continue_from_texts = gr.Button(
                            "Continue to checks",
                            variant="primary",
                            size="lg",
                        )

            with gr.Tab("2. Checks", id="checks"):
                create_select_evaluators_form(state, main_tabs)

            with gr.Tab("3. Settings", id="settings"):
                create_configure_parameters_form(state, main_tabs)

            with gr.Tab("4. Run", id="run"):
                create_analysis(state, main_tabs)

            with gr.Tab("5. Report", id="report"):
                create_overview(state, main_tabs)

        def summarize_state(current_state: DemoState):
            steps = {
                0: "Texts",
                1: "Checks",
                2: "Settings",
                3: "Run",
                4: "Report",
            }
            current = steps.get(current_state.current_step, "Texts")

            completed = []
            if current_state.target_text.text.strip():
                completed.append("Draft added")
            if current_state.copyright_text.text.strip():
                completed.append("Source added")
            if current_state.evaluators:
                completed.append(
                    f"{len(current_state.evaluators)} checks selected"
                )
            if current_state.analysis_complete:
                completed.append("Analysis completed")

            completed_text = " • ".join(completed) if completed else "No progress yet"

            step_md = f"""
### Progress

1. Texts  
2. Checks  
3. Settings  
4. Run  
5. Report

**Current step:** {current}
"""

            status_md = f"""
### Session status

{completed_text}
"""

            return step_md, status_md

        def continue_after_texts(current_state: DemoState):
            if not current_state.target_text.text.strip():
                gr.Warning("Please add the draft text before continuing.")
                return current_state, gr.Tabs(selected="texts")

            if not current_state.copyright_text.text.strip():
                gr.Warning("Please add the source text before continuing.")
                return current_state, gr.Tabs(selected="texts")

            current_state.current_step = 1
            return current_state, gr.Tabs(selected="checks")

        state.change(
            fn=summarize_state,
            inputs=[state],
            outputs=[step_indicator, session_status],
        )

        continue_from_texts.click(
            fn=continue_after_texts,
            inputs=[state],
            outputs=[state, main_tabs],
        )

    return demo