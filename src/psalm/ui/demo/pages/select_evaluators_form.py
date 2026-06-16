from typing import Dict, List

import gradio as gr

from psalm.ui.demo.components.shared import (
    create_panel_title,
    create_secondary_button,
    create_submit_button,
)
from psalm.ui.demo.state import DemoState


def get_evaluator_metadata() -> Dict[str, Dict[str, str]]:
    return {
        "Fast wording checks": {
            "description": (
                "Useful for detecting direct wording overlap and near-verbatim reuse."
            ),
            "evaluators": {
                "BLEU": "Measures wording overlap.",
                "Exact Match": "Checks for exact textual matches.",
                "Rouge": "Measures overlap with the source text.",
            },
        },
        "Writing style checks": {
            "description": (
                "Useful for checking whether the draft sounds stylistically similar."
            ),
            "evaluators": {
                "Writing Style": (
                    "Checks tone, rhythm, sentence style, and expression."
                ),
                "Narrative Voice": (
                    "Checks narrator style and authorial voice."
                ),
            },
        },
        "Story similarity checks": {
            "description": (
                "Useful for reviewing whether the same story elements appear."
            ),
            "evaluators": {
                "Character Similarity": "Checks characters and roles.",
                "Plot Structure": "Checks story beats and structure.",
                "Scene Sequence": "Checks order and progression of scenes.",
                "World Building": "Checks setting and world details.",
            },
        },
        "Context checks": {
            "description": (
                "Useful for contextual factors that may change interpretation."
            ),
            "evaluators": {
                "Parody Satire": "Checks for parody or satire framing.",
                "Pastiche": "Checks for imitation or homage.",
                "Quotation Citation": "Checks quotation and citation signals.",
                "Scenes A Faire": (
                    "Checks whether overlap may be explained by genre convention."
                ),
            },
        },
    }


def create_select_evaluators_form(
    state: gr.State,
    tabs: gr.Tabs,
) -> None:
    metadata = get_evaluator_metadata()

    with gr.Column():
        create_panel_title(
            "Choose checks",
            (
                "Select the types of similarity you want to review. "
                "If you are unsure, start with the recommended checks."
            ),
        )

        recommended = gr.CheckboxGroup(
            label="Recommended starter checks",
            choices=[
                "BLEU",
                "Rouge",
                "Writing Style",
                "Narrative Voice",
            ],
            value=[
                "BLEU",
                "Rouge",
                "Writing Style",
                "Narrative Voice",
            ],
            info="A good default set for most users.",
        )

        with gr.Accordion("More checks", open=False):
            wording_checks = gr.CheckboxGroup(
                label="Fast wording checks",
                choices=list(
                    metadata["Fast wording checks"]["evaluators"].keys()
                ),
                info=metadata["Fast wording checks"]["description"],
            )

            style_checks = gr.CheckboxGroup(
                label="Writing style checks",
                choices=list(
                    metadata["Writing style checks"]["evaluators"].keys()
                ),
                info=metadata["Writing style checks"]["description"],
            )

            story_checks = gr.CheckboxGroup(
                label="Story similarity checks",
                choices=list(
                    metadata["Story similarity checks"]["evaluators"].keys()
                ),
                info=metadata["Story similarity checks"]["description"],
            )

            context_checks = gr.CheckboxGroup(
                label="Context checks",
                choices=list(metadata["Context checks"]["evaluators"].keys()),
                info=metadata["Context checks"]["description"],
            )

        selection_summary = gr.Markdown("No checks selected yet.")

        with gr.Row():
            back_btn = create_secondary_button("Back")
            continue_btn = create_submit_button("Continue to settings")

    def combine_unique(*groups: List[str]) -> list[str]:
        combined: list[str] = []
        for group in groups:
            for item in group or []:
                if item not in combined:
                    combined.append(item)
        return combined

    def render_summary(
        recommended_values: List[str],
        wording_values: List[str],
        style_values: List[str],
        story_values: List[str],
        context_values: List[str],
    ) -> str:
        selected = combine_unique(
            recommended_values,
            wording_values,
            style_values,
            story_values,
            context_values,
        )

        if not selected:
            return "No checks selected yet."

        lines = "\n".join(f"- {item}" for item in selected)
        return f"""
### Selected checks

You selected {len(selected)} check(s):

{lines}
"""

    def handle_back(current_state: DemoState):
        current_state.current_step = 0
        return current_state, gr.Tabs(selected="texts")

    def handle_continue(
        current_state: DemoState,
        recommended_values: List[str],
        wording_values: List[str],
        style_values: List[str],
        story_values: List[str],
        context_values: List[str],
    ):
        selected = combine_unique(
            recommended_values,
            wording_values,
            style_values,
            story_values,
            context_values,
        )

        if not selected:
            gr.Warning("Please select at least one check.")
            return current_state, gr.Tabs(selected="checks"), (
                "No checks selected yet."
            )

        current_state.evaluators = selected
        current_state.current_step = 2
        current_state.reset_analysis()

        return (
            current_state,
            gr.Tabs(selected="settings"),
            render_summary(
                recommended_values,
                wording_values,
                style_values,
                story_values,
                context_values,
            ),
        )

    for component in [
        recommended,
        wording_checks,
        style_checks,
        story_checks,
        context_checks,
    ]:
        component.change(
            fn=render_summary,
            inputs=[
                recommended,
                wording_checks,
                style_checks,
                story_checks,
                context_checks,
            ],
            outputs=[selection_summary],
        )

    back_btn.click(
        fn=handle_back,
        inputs=[state],
        outputs=[state, tabs],
    )

    continue_btn.click(
        fn=handle_continue,
        inputs=[
            state,
            recommended,
            wording_checks,
            style_checks,
            story_checks,
            context_checks,
        ],
        outputs=[state, tabs, selection_summary],
    )