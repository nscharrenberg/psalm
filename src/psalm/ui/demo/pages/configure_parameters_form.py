import os

import gradio as gr

from psalm.ui.demo.components.shared import (
    create_panel_title,
    create_secondary_button,
    create_submit_button,
    create_text_input,
)
from psalm.ui.demo.state import DemoState, EvaluationParameters, LLMParameters


def is_llm_evaluator(evaluator_name: str) -> bool:
    llm_evaluators = [
        "Writing Style",
        "Narrative Voice",
        "Character Similarity",
        "Plot Structure",
        "Scene Sequence",
        "World Building",
        "Parody Satire",
        "Pastiche",
        "Quotation Citation",
        "Scenes A Faire",
    ]
    return evaluator_name in llm_evaluators


def create_configure_parameters_form(
    state: gr.State,
    tabs: gr.Tabs,
) -> None:
    with gr.Column():
        create_panel_title(
            "Review settings",
            (
                "Most users can keep the default settings. "
                "Only advanced users usually need to change them."
            ),
        )

        selected_checks = gr.Markdown("No checks selected yet.")

        with gr.Group():
            gr.Markdown("### Basic options")
            debug_mode = gr.Checkbox(
                label="Show detailed logs",
                value=False,
                info="Useful for troubleshooting and tracing evaluator output.",
            )

        with gr.Accordion("Advanced performance settings", open=False):
            with gr.Row():
                max_concurrency = gr.Slider(
                    label="Max concurrency",
                    minimum=1,
                    maximum=50,
                    step=1,
                    value=1,
                )
                timeout = gr.Slider(
                    label="Timeout (seconds)",
                    minimum=30,
                    maximum=3600,
                    step=10,
                    value=300,
                )

            wait_time = gr.Slider(
                label="Wait time between checks (seconds)",
                minimum=0.1,
                maximum=120.0,
                step=0.1,
                value=1.0,
            )

        with gr.Group(visible=False) as llm_group:
            gr.Markdown("### AI settings")
            gr.Markdown(
                (
                    "Some checks use an AI model. "
                    "If those are selected, fill in the settings below."
                )
            )

            model_name = gr.Dropdown(
                label="Model",
                choices=[
                    "gpt-5-nano",
                    "gpt-5-mini",
                    "gpt-5",
                    "gpt-4o-mini",
                    "gpt-5.4-nano",
                    "gpt-5.4-mini",
                    "gpt-5.4",
                    "gpt-5.5",
                    "gpt-5.5-pro",
                ],
                value="gpt-5-nano",
            )

            api_key = create_text_input(
                "API key",
                placeholder="Enter OpenAI API key",
                password=True,
            )

            with gr.Accordion("Advanced AI settings", open=False):
                base_url = create_text_input(
                    "Base URL",
                    placeholder="Optional custom endpoint",
                )
                temperature = gr.Slider(
                    label="Temperature",
                    minimum=0.0,
                    maximum=2.0,
                    value=0.1,
                    step=0.1,
                )

        summary = gr.Markdown("Default settings will be used.")

        with gr.Row():
            back_btn = create_secondary_button("Back")
            continue_btn = create_submit_button("Continue to run")

    def build_summary(
        current_state: DemoState,
        max_conc: float,
        wait_value: float,
        timeout_value: float,
        debug_value: bool,
        model_value: str,
        api_key_value: str,
        base_url_value: str,
        temp_value: float,
    ) -> str:
        selected = current_state.evaluators or []
        has_llm = any(is_llm_evaluator(item) for item in selected)

        selected_lines = "\n".join(f"- {item}" for item in selected) or "- None"

        text = f"""
### Current configuration

**Checks**
{selected_lines}

**Basic options**
- Detailed logs: {"Enabled" if debug_value else "Disabled"}

**Performance**
- Max concurrency: {int(max_conc)}
- Timeout: {int(timeout_value)} seconds
- Wait time: {wait_value:.1f} seconds
"""

        if has_llm:
            api_status = (
                "Provided"
                if (api_key_value and api_key_value.strip())
                or os.getenv("OPENAI_API_KEY")
                else "Not provided"
            )

            text += f"""

**AI settings**
- Model: {model_value}
- API key: {api_status}
- Base URL: {base_url_value if base_url_value else "Default"}
- Temperature: {temp_value:.1f}
"""

        return text

    def update_state_view(current_state: DemoState):
        selected = current_state.evaluators or []
        selected_md = "\n".join(f"- {item}" for item in selected) or "- None"

        has_llm = any(is_llm_evaluator(item) for item in selected)

        return (
            f"### Checks selected\n{selected_md}",
            gr.update(visible=has_llm),
            build_summary(
                current_state,
                max_concurrency.value,
                wait_time.value,
                timeout.value,
                debug_mode.value,
                model_name.value,
                api_key.value or "",
                base_url.value or "",
                temperature.value,
            ),
        )

    def update_summary_live(
        current_state: DemoState,
        max_conc: float,
        wait_value: float,
        timeout_value: float,
        debug_value: bool,
        model_value: str,
        api_key_value: str,
        base_url_value: str,
        temp_value: float,
    ):
        return build_summary(
            current_state,
            max_conc,
            wait_value,
            timeout_value,
            debug_value,
            model_value,
            api_key_value or "",
            base_url_value or "",
            temp_value,
        )

    def handle_back(current_state: DemoState):
        current_state.current_step = 1
        return current_state, gr.Tabs(selected="checks")

    def handle_continue(
        current_state: DemoState,
        max_conc: float,
        wait_value: float,
        timeout_value: float,
        debug_value: bool,
        model_value: str,
        api_key_value: str,
        base_url_value: str,
        temp_value: float,
    ):
        has_llm = any(
            is_llm_evaluator(item)
            for item in (current_state.evaluators or [])
        )

        if has_llm and (
            (not api_key_value or not api_key_value.strip())
            and not os.getenv("OPENAI_API_KEY")
        ):
            gr.Warning(
                "Please provide an API key for the AI-based checks, or set "
                "OPENAI_API_KEY in the environment."
            )
            return current_state, gr.Tabs(selected="settings"), (
                build_summary(
                    current_state,
                    max_conc,
                    wait_value,
                    timeout_value,
                    debug_value,
                    model_value,
                    api_key_value or "",
                    base_url_value or "",
                    temp_value,
                )
            )

        current_state.evaluation_params = EvaluationParameters(
            llm_params=LLMParameters(
                model_name=model_value,
                base_url=base_url_value.strip()
                or "https://api.openai.com/v1",
                api_key=(
                    api_key_value.strip()
                    if api_key_value and api_key_value.strip()
                    else os.getenv("OPENAI_API_KEY", "")
                ),
                temperature=float(temp_value),
            ),
            max_concurrency=int(max_conc),
            wait_time=float(wait_value),
            timeout=float(timeout_value),
            debug=bool(debug_value),
        )
        current_state.current_step = 3
        current_state.reset_analysis()

        return (
            current_state,
            gr.Tabs(selected="run"),
            build_summary(
                current_state,
                max_conc,
                wait_value,
                timeout_value,
                debug_value,
                model_value,
                api_key_value or "",
                base_url_value or "",
                temp_value,
            ),
        )

    state.change(
        fn=update_state_view,
        inputs=[state],
        outputs=[selected_checks, llm_group, summary],
    )

    for component in [
        max_concurrency,
        wait_time,
        timeout,
        debug_mode,
        model_name,
        api_key,
        base_url,
        temperature,
    ]:
        component.change(
            fn=update_summary_live,
            inputs=[
                state,
                max_concurrency,
                wait_time,
                timeout,
                debug_mode,
                model_name,
                api_key,
                base_url,
                temperature,
            ],
            outputs=[summary],
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
            max_concurrency,
            wait_time,
            timeout,
            debug_mode,
            model_name,
            api_key,
            base_url,
            temperature,
        ],
        outputs=[state, tabs, summary],
    )