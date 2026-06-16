import json
from typing import Any

import gradio as gr


def create_text_input(
    label: str,
    placeholder: str = "",
    lines: int = 1,
    info: str | None = None,
    value: str = "",
    password: bool = False,
) -> gr.Textbox:
    return gr.Textbox(
        label=label,
        placeholder=placeholder,
        lines=lines,
        info=info,
        value=value,
        type="password" if password else "text",
    )


def create_dropdown(
    label: str,
    choices: list,
    value: Any = None,
    info: str | None = None,
) -> gr.Dropdown:
    return gr.Dropdown(
        label=label,
        choices=choices,
        value=value,
        info=info,
    )


def create_submit_button(
    text: str = "Submit",
    variant: str = "primary",
    size: str = "lg",
) -> gr.Button:
    return gr.Button(text, variant=variant, size=size)


def create_secondary_button(
    text: str,
    size: str = "lg",
) -> gr.Button:
    return gr.Button(text, variant="secondary", size=size)


def create_panel_title(
    title: str,
    description: str | None = None,
) -> None:
    text = f"## {title}"
    if description:
        text += f"\n\n{description}"
    gr.Markdown(text)


def create_readonly_textbox(
    label: str,
    value: str = "",
    lines: int = 3,
) -> gr.Textbox:
    return gr.Textbox(
        label=label,
        value=value,
        lines=lines,
        interactive=False,
    )


def safe_json_pretty(value: Any) -> str:
    try:
        return json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
            sort_keys=True,
        )
    except Exception:
        return str(value)


def as_markdown_kv_table(title: str, data: dict[str, Any]) -> str:
    if not data:
        return f"### {title}\n\n_No data available._"

    lines = [f"### {title}", "", "| Field | Value |", "|---|---|"]
    for key, value in data.items():
        rendered = str(value).replace("\n", "<br>")
        lines.append(f"| {key} | {rendered} |")

    return "\n".join(lines)