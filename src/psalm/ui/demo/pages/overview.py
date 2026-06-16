from typing import Any

import gradio as gr

from psalm.ui.demo.components.shared import (
    create_secondary_button,
    safe_json_pretty,
)
from psalm.ui.demo.state import DemoState


def create_overview(
    state: gr.State,
    tabs: gr.Tabs,
) -> None:
    with gr.Column():
        gr.Markdown(
            """
## Report

This report turns the raw analysis into a readable summary for reviewers.

It is intended to help answer:
- does the draft appear too close to the source?
- which aspects look most concerning?
- what evidence and reasoning led to those results?
"""
        )

        overall_result = gr.Markdown("No report available yet.")
        report_summary = gr.Markdown("")

        with gr.Row():
            average_score_box = gr.Textbox(
                label="Average similarity score",
                interactive=False,
            )
            highest_score_box = gr.Textbox(
                label="Highest similarity score",
                interactive=False,
            )
            checks_run_box = gr.Textbox(
                label="Checks run",
                interactive=False,
            )

        score_table = gr.Dataframe(
            headers=["Check", "Score", "Level", "Meaning"],
            datatype=["str", "str", "str", "str"],
            row_count=0,
            column_count=4,
            interactive=False,
            label="Results by check",
        )

        with gr.Row():
            higher_concern = gr.Textbox(
                label="Areas of higher concern",
                interactive=False,
                lines=8,
            )
            lower_concern = gr.Textbox(
                label="Areas of lower concern",
                interactive=False,
                lines=8,
            )

        with gr.Accordion("Detailed explanations", open=False):
            detailed_reasoning = gr.Markdown("")

        with gr.Accordion("Per-check trace view", open=False):
            result_selector = gr.Dropdown(
                label="Select a check",
                choices=[],
                value=None,
            )

            trace_summary = gr.Markdown("Select a check to inspect its trace.")
            trace_reason = gr.Markdown("")
            trace_details = gr.JSON(label="Structured details", value={})
            trace_verbose_logs = gr.TextArea(
                label="Verbose logs",
                value="",
                interactive=False,
                lines=18,
            )
            trace_raw_result = gr.TextArea(
                label="Raw result JSON",
                value="",
                interactive=False,
                lines=18,
            )

        with gr.Accordion("Texts reviewed", open=False):
            with gr.Row():
                with gr.Column():
                    draft_title = gr.Textbox(
                        label="Draft title",
                        interactive=False,
                    )
                    draft_author = gr.Textbox(
                        label="Draft author",
                        interactive=False,
                    )
                    draft_text = gr.TextArea(
                        label="Draft text",
                        interactive=False,
                        lines=12,
                    )
                with gr.Column():
                    source_title = gr.Textbox(
                        label="Source title",
                        interactive=False,
                    )
                    source_author = gr.Textbox(
                        label="Source author",
                        interactive=False,
                    )
                    source_text = gr.TextArea(
                        label="Source text",
                        interactive=False,
                        lines=12,
                    )

        with gr.Accordion("Settings used", open=False):
            settings_used = gr.Markdown("")

        with gr.Accordion("Technical activity log", open=False):
            technical_log = gr.Textbox(
                label="Log",
                interactive=False,
                lines=14,
            )

        back_btn = create_secondary_button("Back to run screen")

    def score_band(score: float) -> tuple[str, str]:
        if score < 0:
            return "Error", "The check did not complete successfully"
        if score >= 0.9:
            return "Very high", "Very strong similarity signal"
        if score >= 0.7:
            return "High", "Strong similarity signal"
        if score >= 0.4:
            return "Medium", "Moderate similarity signal"
        if score >= 0.2:
            return "Low", "Limited similarity signal"
        return "Very low", "Little or no meaningful similarity signal"

    def overall_conclusion(scores: list[float]) -> tuple[str, str]:
        valid_scores = [score for score in scores if score >= 0]
        if not valid_scores:
            return (
                "### No successful results available",
                "The analysis did not produce successful scores.",
            )

        avg_score = sum(valid_scores) / len(valid_scores)
        max_score = max(valid_scores)

        if max_score >= 0.9 or avg_score >= 0.75:
            return (
                "### Overall outcome: High concern",
                (
                    "The draft shows strong similarity signals in one or more "
                    "important areas. A closer editorial and possibly legal "
                    "review is recommended."
                ),
            )

        if max_score >= 0.7 or avg_score >= 0.5:
            return (
                "### Overall outcome: Moderate concern",
                (
                    "The draft shows meaningful similarity to the source in "
                    "some areas. It would be prudent to review the flagged "
                    "aspects carefully."
                ),
            )

        if max_score >= 0.4 or avg_score >= 0.25:
            return (
                "### Overall outcome: Limited concern",
                (
                    "Some overlap or resemblance was detected, but the signals "
                    "are mixed or moderate rather than consistently strong."
                ),
            )

        return (
            "### Overall outcome: Low concern",
            (
                "The selected checks did not find strong similarity signals "
                "overall."
            ),
        )

    def build_report(current_state: DemoState):
        if not current_state.results:
            return (
                "No report available yet.",
                "",
                "",
                "",
                "",
                [],
                "No higher-concern areas identified.",
                "No lower-concern areas identified.",
                "",
                gr.update(choices=[], value=None),
                "Select a check to inspect its trace.",
                "",
                {},
                "",
                "",
                current_state.target_text.title,
                current_state.target_text.author,
                current_state.target_text.text,
                current_state.copyright_text.title,
                current_state.copyright_text.author,
                current_state.copyright_text.text,
                "",
                current_state.console_log or "",
            )

        scores = []
        table_rows = []
        higher_items = []
        lower_items = []
        reasoning_sections = []

        selector_choices = []

        for item in current_state.results:
            evaluator = str(item.get("evaluator", "Unknown"))
            score = float(item.get("score", 0.0))
            reason = item.get("reason") or "No explanation provided."
            level, meaning = score_band(score)

            selector_choices.append(evaluator)
            scores.append(score)

            table_rows.append(
                [
                    evaluator,
                    f"{score:.4f}" if score >= 0 else "Error",
                    level,
                    meaning,
                ]
            )

            if score >= 0.7:
                higher_items.append(
                    f"- {evaluator}: {score:.4f} ({meaning})"
                )
            else:
                if score >= 0:
                    lower_items.append(
                        f"- {evaluator}: {score:.4f} ({meaning})"
                    )
                else:
                    lower_items.append(f"- {evaluator}: Error")

            reasoning_sections.append(
                f"### {evaluator}\n"
                f"- Score: **{f'{score:.4f}' if score >= 0 else 'Error'}**\n"
                f"- Level: **{level}**\n"
                f"- Meaning: {meaning}\n"
                f"- Explanation: {reason}\n"
            )

        valid_scores = [score for score in scores if score >= 0]
        avg_score = (
            sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
        )
        max_score = max(valid_scores) if valid_scores else 0.0

        verdict_title, verdict_body = overall_conclusion(scores)

        summary = f"""
{verdict_body}

**Important note:** this tool supports editorial review and triage. It does
not by itself determine legal infringement.
"""

        settings_text = f"""
### Settings used

- Checks run: {", ".join(current_state.evaluators) if current_state.evaluators else "None"}
- Max concurrency: {current_state.evaluation_params.max_concurrency}
- Timeout: {int(current_state.evaluation_params.timeout)} seconds
- Wait time: {current_state.evaluation_params.wait_time:.1f} seconds
- Detailed logs: {"Enabled" if current_state.evaluation_params.debug else "Disabled"}
- AI model: {current_state.evaluation_params.llm_params.model_name or "Not used"}
- Base URL: {current_state.evaluation_params.llm_params.base_url or "Default"}
- Temperature: {current_state.evaluation_params.llm_params.temperature:.1f}
"""

        return (
            verdict_title,
            summary,
            f"{avg_score:.4f}" if valid_scores else "N/A",
            f"{max_score:.4f}" if valid_scores else "N/A",
            str(len(current_state.results)),
            table_rows,
            "\n".join(higher_items)
            if higher_items
            else "No higher-concern areas identified.",
            "\n".join(lower_items)
            if lower_items
            else "No lower-concern areas identified.",
            "\n\n".join(reasoning_sections),
            gr.update(
                choices=selector_choices,
                value=selector_choices[0] if selector_choices else None,
            ),
            "Select a check to inspect its trace.",
            "",
            {},
            "",
            "",
            current_state.target_text.title,
            current_state.target_text.author,
            current_state.target_text.text,
            current_state.copyright_text.title,
            current_state.copyright_text.author,
            current_state.copyright_text.text,
            settings_text,
            current_state.console_log or "",
        )

    def build_trace_view(current_state: DemoState, selected_evaluator: str):
        if not current_state.results or not selected_evaluator:
            return (
                "Select a check to inspect its trace.",
                "",
                {},
                "",
                "",
            )

        selected = None
        for item in current_state.results:
            if item.get("evaluator") == selected_evaluator:
                selected = item
                break

        if not selected:
            return (
                "The selected check could not be found.",
                "",
                {},
                "",
                "",
            )

        score = float(selected.get("score", 0.0))
        level, meaning = score_band(score)
        confidence = selected.get("confidence")
        timestamp = selected.get("timestamp")
        reason = selected.get("reason") or "No explanation provided."
        details = selected.get("details") or {}
        verbose_logs = selected.get("verbose_logs")
        raw_result = selected.get("raw_result")

        summary = f"""
### Trace summary

- Check: **{selected_evaluator}**
- Score: **{f"{score:.4f}" if score >= 0 else "Error"}**
- Level: **{level}**
- Meaning: {meaning}
- Confidence: {confidence if confidence is not None else "Not provided"}
- Timestamp: {timestamp if timestamp is not None else "Not provided"}
"""

        reason_md = f"""
### Model explanation

{reason}
"""

        verbose_text = ""
        if verbose_logs is None:
            verbose_text = "No verbose logs were provided for this result."
        elif isinstance(verbose_logs, str):
            verbose_text = verbose_logs
        elif isinstance(verbose_logs, list):
            verbose_text = "\n\n".join(str(item) for item in verbose_logs)
        else:
            verbose_text = safe_json_pretty(verbose_logs)

        raw_result_text = (
            safe_json_pretty(raw_result)
            if raw_result is not None
            else "No raw result available."
        )

        return (
            summary,
            reason_md,
            details,
            verbose_text,
            raw_result_text,
        )

    def go_back(current_state: DemoState):
        current_state.current_step = 3
        return current_state, gr.Tabs(selected="run")

    state.change(
        fn=build_report,
        inputs=[state],
        outputs=[
            overall_result,
            report_summary,
            average_score_box,
            highest_score_box,
            checks_run_box,
            score_table,
            higher_concern,
            lower_concern,
            detailed_reasoning,
            result_selector,
            trace_summary,
            trace_reason,
            trace_details,
            trace_verbose_logs,
            trace_raw_result,
            draft_title,
            draft_author,
            draft_text,
            source_title,
            source_author,
            source_text,
            settings_used,
            technical_log,
        ],
    )

    result_selector.change(
        fn=build_trace_view,
        inputs=[state, result_selector],
        outputs=[
            trace_summary,
            trace_reason,
            trace_details,
            trace_verbose_logs,
            trace_raw_result,
        ],
    )

    back_btn.click(
        fn=go_back,
        inputs=[state],
        outputs=[state, tabs],
    )