import gradio as gr

from psalm.ui.demo.components.shared import (
    create_dropdown,
    create_panel_title,
    create_submit_button,
)
from psalm.ui.demo.examples import get_examples
from psalm.ui.demo.state import DemoState


def create_example_selection_form(
    state: gr.State,
    tabs: gr.Tabs,
) -> None:
    examples = get_examples()
    example_names = [example.name for example in examples]

    with gr.Group():
        create_panel_title(
            "Use a prepared example",
            (
                "Load a pre-made scenario to test the workflow quickly. "
                "This will fill in both the draft and the source text."
            ),
        )

        example_dropdown = create_dropdown(
            label="Example scenario",
            choices=example_names,
            value=None,
            info="Choose a scenario to load.",
        )

        variant_dropdown = create_dropdown(
            label="Similarity level",
            choices=[],
            value=None,
            info="Choose how similar the draft should be to the source.",
        )

        preview_box = gr.Markdown(
            "Select an example to preview the source and draft."
        )

        load_btn = create_submit_button("Load example and continue")

    def get_example_by_name(example_name: str):
        for example in get_examples():
            if example.name == example_name:
                return example
        return None

    def update_variant_choices(example_name: str):
        example = get_example_by_name(example_name)
        if not example:
            return gr.update(choices=[], value=None), "No example selected."

        choices = [variant.severity.value for variant in example.variants]
        value = choices[0] if choices else None
        return (
            gr.update(choices=choices, value=value),
            "Choose a similarity level to preview the texts.",
        )

    def update_preview(example_name: str, variant_name: str):
        example = get_example_by_name(example_name)
        if not example:
            return "No example selected."

        chosen_variant = None
        for variant in example.variants:
            if variant.severity.value == variant_name:
                chosen_variant = variant
                break

        if not chosen_variant:
            return "Choose a similarity level to preview the texts."

        source_preview = example.copyright_text.text.strip()
        target_preview = chosen_variant.text.text.strip()

        source_preview = (
            source_preview[:280] + "..."
            if len(source_preview) > 280
            else source_preview
        )
        target_preview = (
            target_preview[:280] + "..."
            if len(target_preview) > 280
            else target_preview
        )

        return f"""
### Example preview

**Source text**
- Title: {example.copyright_text.title or "Not provided"}
- Author: {example.copyright_text.author or "Not provided"}

> {source_preview}

**Draft text**
- Similarity level: {chosen_variant.severity.value}

> {target_preview}
"""

    def handle_load(
        current_state: DemoState,
        example_name: str,
        variant_name: str,
    ):
        if not example_name or not variant_name:
            gr.Warning("Please choose both an example and a similarity level.")
            return current_state, gr.Tabs(selected="texts")

        example = get_example_by_name(example_name)
        if not example:
            gr.Warning("The selected example could not be found.")
            return current_state, gr.Tabs(selected="texts")

        chosen_variant = None
        for variant in example.variants:
            if variant.severity.value == variant_name:
                chosen_variant = variant
                break

        if not chosen_variant:
            gr.Warning("The selected similarity level could not be found.")
            return current_state, gr.Tabs(selected="texts")

        current_state.target_text = chosen_variant.text
        current_state.copyright_text = example.copyright_text
        current_state.current_step = 1
        current_state.reset_analysis()

        return current_state, gr.Tabs(selected="checks")

    example_dropdown.change(
        fn=update_variant_choices,
        inputs=[example_dropdown],
        outputs=[variant_dropdown, preview_box],
    )

    variant_dropdown.change(
        fn=update_preview,
        inputs=[example_dropdown, variant_dropdown],
        outputs=[preview_box],
    )

    load_btn.click(
        fn=handle_load,
        inputs=[state, example_dropdown, variant_dropdown],
        outputs=[state, tabs],
    )