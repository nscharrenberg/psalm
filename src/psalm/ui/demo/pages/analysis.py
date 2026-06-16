import os
import time
from typing import Any, Optional

import gradio as gr

from psalm import AnonymousText, Book, Result
from psalm.evaluators.base_evaluator import BaseEvaluator
from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator
from psalm.ui.demo.pages.configure_parameters_form import is_llm_evaluator
from psalm.ui.demo.state import DemoState


def get_evaluator_class(evaluator_name: str) -> Optional[BaseEvaluator]:
    try:
        evaluator_classes = {
            "BLEU": (
                "psalm.evaluators.computational.lexical.bleu_evaluator",
                "BleuEvaluator",
            ),
            "Exact Match": (
                "psalm.evaluators.computational.lexical.exact_match_evaluator",
                "ExactMatchEvaluator",
            ),
            "Rouge": (
                "psalm.evaluators.computational.lexical.rouge_evaluator",
                "RougeEvaluator",
            ),
            "Writing Style": (
                "psalm.evaluators.llm.stylistic.writing_style_evaluator",
                "WritingStyleEvaluator",
            ),
            "Narrative Voice": (
                "psalm.evaluators.llm.stylistic.narrative_voice_evaluator",
                "NarrativeVoiceEvaluator",
            ),
            "Character Similarity": (
                "psalm.evaluators.llm.narrative.character_similarity_evaluator",
                "CharacterSimilarityEvaluator",
            ),
            "Plot Structure": (
                "psalm.evaluators.llm.narrative.plot_structure_evaluator",
                "PlotStructureSimilarityEvaluator",
            ),
            "Scene Sequence": (
                "psalm.evaluators.llm.narrative.scene_sequence_similarity_evaluator",
                "SceneSequenceSimilarityEvaluator",
            ),
            "World Building": (
                "psalm.evaluators.llm.narrative.world_building_similarity",
                "WorldBuildingSimilarityEvaluator",
            ),
            "Parody Satire": (
                "psalm.evaluators.llm.exceptions.parody_satire_evaluator",
                "ParodySatireEvaluator",
            ),
            "Pastiche": (
                "psalm.evaluators.llm.exceptions.pastiche_evaluator",
                "PasticheEvaluator",
            ),
            "Quotation Citation": (
                "psalm.evaluators.llm.exceptions.quotation_citation_evaluator",
                "QuotationCitationEvaluator",
            ),
            "Scenes A Faire": (
                "psalm.evaluators.llm.exceptions.scenes_a_faire_evaluator",
                "ScenesAFaireEvaluator",
            ),
        }

        if evaluator_name in evaluator_classes:
            module_path, class_name = evaluator_classes[evaluator_name]
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            return cls()
    except Exception as e:
        print(f"Error getting evaluator class for {evaluator_name}: {e}")

    return None


def normalize_result(
    evaluator_name: str,
    result: Result,
) -> dict[str, Any]:
    raw = result.model_dump()

    details = raw.get("details") or {}
    if details is None:
        details = {}

    verbose_logs = (
        details.get("verbose_logs")
        or details.get("verbose_log")
        or details.get("logs")
        or None
    )

    normalized = {
        "evaluator": evaluator_name,
        "score": float(raw.get("score", 0.0)),
        "confidence": raw.get("confidence"),
        "reason": raw.get("reason"),
        "timestamp": raw.get("timestamp"),
        "details": details,
        "verbose_logs": verbose_logs,
        "raw_result": raw,
    }

    return normalized


def create_analysis(
    state: gr.State,
    tabs: gr.Tabs,
) -> None:
    with gr.Column():
        gr.Markdown(
            """
## Run analysis

Review the summary below, then start the analysis.
"""
        )

        run_summary = gr.Markdown("Waiting for configuration...")
        start_btn = gr.Button("Start analysis", variant="primary", size="lg")

        with gr.Group():
            progress_status = gr.Markdown("Analysis has not started yet.")
            progress_bar = gr.Slider(
                label="Progress",
                minimum=0,
                maximum=100,
                value=0,
                step=1,
                interactive=False,
            )

        with gr.Accordion("Detailed activity log", open=False):
            console_log = gr.TextArea(
                label="Log",
                value="",
                interactive=False,
                lines=16,
            )

        raw_results = gr.JSON(label="Normalized results", value=[])

        with gr.Row():
            back_btn = gr.Button("Back", variant="secondary")
            open_report_btn = gr.Button(
                "Open report",
                variant="secondary",
            )

    def build_run_summary(current_state: DemoState) -> str:
        target = current_state.target_text
        source = current_state.copyright_text
        evaluators = current_state.evaluators or []
        params = current_state.evaluation_params

        checks_md = "\n".join(f"- {item}" for item in evaluators) or "- None"

        has_llm = any(is_llm_evaluator(item) for item in evaluators)
        llm_text = ""
        if has_llm:
            llm_text = f"""

**AI configuration**
- Model: {params.llm_params.model_name}
- Base URL: {params.llm_params.base_url or "Default"}
- API key: {"Provided" if params.llm_params.api_key or os.getenv("OPENAI_API_KEY") else "Not provided"}
- Temperature: {params.llm_params.temperature:.1f}
"""

        return f"""
### Analysis summary

**Draft**
- Title: {target.title or "Not provided"}
- Author: {target.author or "Not provided"}
- Length: {len(target.text)} characters

**Source**
- Title: {source.title or "Not provided"}
- Author: {source.author or "Not provided"}
- Length: {len(source.text)} characters

**Checks**
{checks_md}

**Performance**
- Max concurrency: {params.max_concurrency}
- Timeout: {int(params.timeout)} seconds
- Wait time: {params.wait_time:.1f} seconds
- Detailed logs: {"Enabled" if params.debug else "Disabled"}
{llm_text}
"""

    def update_summary(current_state: DemoState):
        return build_run_summary(current_state)

    def go_back(current_state: DemoState):
        current_state.current_step = 2
        return current_state, gr.Tabs(selected="settings")

    def open_report(current_state: DemoState):
        if not current_state.results:
            gr.Warning("Run the analysis first.")
            return current_state, gr.Tabs(selected="run")

        current_state.current_step = 4
        return current_state, gr.Tabs(selected="report")

    state.change(
        fn=update_summary,
        inputs=[state],
        outputs=[run_summary],
    )

    back_btn.click(
        fn=go_back,
        inputs=[state],
        outputs=[state, tabs],
    )

    open_report_btn.click(
        fn=open_report,
        inputs=[state],
        outputs=[state, tabs],
    )

    def handle_analysis(current_state: DemoState):
        if not current_state.target_text.text.strip():
            gr.Warning("Please add a draft text first.")
            yield (
                current_state,
                "Please add a draft text first.",
                gr.update(value=0),
                current_state.console_log,
                current_state.results,
                gr.Tabs(selected="run"),
            )
            return

        if not current_state.copyright_text.text.strip():
            gr.Warning("Please add a source text first.")
            yield (
                current_state,
                "Please add a source text first.",
                gr.update(value=0),
                current_state.console_log,
                current_state.results,
                gr.Tabs(selected="run"),
            )
            return

        if not current_state.evaluators:
            gr.Warning("Please select at least one check first.")
            yield (
                current_state,
                "Please select at least one check first.",
                gr.update(value=0),
                current_state.console_log,
                current_state.results,
                gr.Tabs(selected="run"),
            )
            return

        current_state.reset_analysis()
        current_state.is_analysis_running = True
        current_state.current_step = 3
        current_state.append_log("Analysis started.")

        target_book = AnonymousText(text=current_state.target_text.text)
        source_book = Book(
            title=current_state.copyright_text.title,
            author=current_state.copyright_text.author,
            text=current_state.copyright_text.text,
            language="en",
        )

        total = len(current_state.evaluators)

        yield (
            current_state,
            "Analysis started.",
            gr.update(value=0),
            current_state.console_log,
            current_state.results,
            gr.Tabs(selected="run"),
        )

        for idx, evaluator_name in enumerate(current_state.evaluators, start=1):
            current_state.append_log(
                f"Running {evaluator_name} ({idx}/{total})..."
            )

            yield (
                current_state,
                f"Running check {idx} of {total}: {evaluator_name}",
                gr.update(value=int(((idx - 1) / total) * 100)),
                current_state.console_log,
                current_state.results,
                gr.Tabs(selected="run"),
            )

            try:
                evaluator_cls = get_evaluator_class(evaluator_name)
                if not evaluator_cls:
                    raise ValueError(
                        f"Evaluator class not found for {evaluator_name}"
                    )

                form_api_key = current_state.evaluation_params.llm_params.api_key

                if isinstance(evaluator_cls, BaseDagEvaluator):
                    if form_api_key and form_api_key.strip():
                        os.environ["OPENAI_API_KEY"] = form_api_key.strip()
                    elif os.getenv("OPENAI_API_KEY") is None:
                        raise ValueError(
                            f"API key not set for evaluator {evaluator_name}"
                        )

                result: Result = evaluator_cls.evaluate(
                    source_book,
                    target_book,
                    model_name=current_state.evaluation_params.llm_params.model_name,
                    debug=current_state.evaluation_params.debug,
                )

                normalized_result = normalize_result(evaluator_name, result)
                current_state.results.append(normalized_result)

                current_state.append_log(
                    f"Completed {evaluator_name} "
                    f"with score {normalized_result['score']:.4f}."
                )
            except Exception as e:
                current_state.results.append(
                    {
                        "evaluator": evaluator_name,
                        "score": -1.0,
                        "confidence": None,
                        "reason": f"Error: {str(e)}",
                        "timestamp": None,
                        "details": {"error": str(e)},
                        "verbose_logs": None,
                        "raw_result": None,
                    }
                )
                current_state.append_log(
                    f"Error during {evaluator_name}: {str(e)}"
                )

            yield (
                current_state,
                f"Completed {idx} of {total} checks.",
                gr.update(value=int((idx / total) * 100)),
                current_state.console_log,
                current_state.results,
                gr.Tabs(selected="run"),
            )

            if current_state.evaluation_params.wait_time > 0 and idx < total:
                current_state.append_log(
                    "Waiting "
                    f"{current_state.evaluation_params.wait_time:.1f} seconds "
                    "before the next check."
                )
                yield (
                    current_state,
                    "Preparing next check...",
                    gr.update(value=int((idx / total) * 100)),
                    current_state.console_log,
                    current_state.results,
                    gr.Tabs(selected="run"),
                )
                time.sleep(current_state.evaluation_params.wait_time)

        current_state.analysis_complete = True
        current_state.is_analysis_running = False
        current_state.current_step = 4
        current_state.append_log("Analysis completed.")

        yield (
            current_state,
            "Analysis completed. You can now open the report.",
            gr.update(value=100),
            current_state.console_log,
            current_state.results,
            gr.Tabs(selected="report"),
        )

    start_btn.click(
        fn=handle_analysis,
        inputs=[state],
        outputs=[
            state,
            progress_status,
            progress_bar,
            console_log,
            raw_results,
            tabs,
        ],
    )