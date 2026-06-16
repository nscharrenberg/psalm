from dataclasses import dataclass, field
from typing import Optional

from psalm.utils.env_utils import get_env_by_name_or_default


@dataclass
class QuestionVerbatimAnswerGeneratorConfig:
    min_amount_of_questions_per_book: Optional[int] = field(default_factory=lambda: get_env_by_name_or_default("SDG_QUESTION_VERBATIM_ANSWER_MIN_AMOUNT_OF_QUESTIONS", 1, int))
    max_amount_of_questions_per_book: Optional[int] = field(default_factory=lambda: get_env_by_name_or_default("SDG_QUESTION_VERBATIM_ANSWER_MAX_AMOUNT_OF_QUESTIONS", None, int))
    instruction: str = field(default_factory=lambda: get_env_by_name_or_default("SDG_QUESTION_VERBATIM_ANSWER_PROMPT_TEMPLATE", """
You are an extraction model that generates writing-assignment prompts paired with verbatim exemplars from a given book text.

Metadata
- Book title: "{book_title}"
- Author: "{book_author}"

Objective
- Produce items where:
  - assignment: an instruction-style writing prompt (not a question) explicitly invoking the style of "{book_title}" by {book_author}.
  - exemplar: a verbatim, contiguous excerpt from the Text that fulfills the assignment.
- Prefer coherent narrative segments (scenes, dialogues, inner thoughts, descriptive passages).
- Each exemplar must be approximately (but less then) 1024 characters. If a longer span would fit better, choose the most self-contained sub-span ≤ 1024 chars.

Language policy (mandatory)
- Write all assignments in the same language as the Text.
- Exemplars are verbatim spans from the Text and thus in that language.
- If the Text is mixed-language, for each item: assignment language = dominant language of the selected passage; exemplar from that same language.
- If you cannot confidently determine the Text’s language, produce no output.

Hard constraints (must follow)
- Use only the provided Text; no external knowledge.
- Exemplars must be contiguous spans (no stitching).
- Preserve original punctuation/capitalization/spelling/line breaks (trim leading/trailing whitespace only).
- Do not invent content. If no suitable span exists, SKIP the item (return fewer items).

Assignment style (required)
- Imperative instructions only (e.g., "Write…", "Compose…", "Draft…", "Create…"). Do not ask questions.
- Every assignment MUST explicitly mention "{book_title}" and {book_author}.
- Vary assignment types and focal characters across items.

Assignment–Exemplar alignment (hard)
- The exemplar MUST concretely satisfy the assignment’s scenario, actors, and requested mode:
  - If the assignment requests a dialogue between X and Y, the span must contain dialogue with both X and Y speaking/acting.
  - If it requests a monologue by [Character], the span must be dominated by that character’s speech/thought.
  - If it requests a descriptive passage of [setting/mood], the span must be descriptive prose about that setting/mood (not a list/header).
  - If specific characters or roles are named in the assignment, they must appear in the exemplar beyond mere mention in a list.
- If no contiguous span satisfies the assignment, SKIP it.

Exemplar exclusion rules (hard)
- Do NOT select cast lists, dramatis personae, role/name lists, or character rosters.
- Do NOT select chapter/scene headings or bare location lines (e.g., "The scene takes place in …", "Scene: …", "Setting: …").
- Do NOT select isolated stage directions without surrounding narrative/dialogue.
- Do NOT select exemplars shorter than 80 characters unless no longer coherent span exists.

Exemplar formatting rules
- Copy the excerpt verbatim; do not add or remove words.
- Length limit: ≤ 1024 characters.
- Prefer complete sentences; avoid truncating mid-word. If needed, back off to the prior sentence boundary.

Coverage and diversity
- Cover different scenes, characters, locations, and themes.
- Do not reuse the same passage across items.
- If the Text chunk is mostly front matter or lists, produce fewer items or none.

Negative examples (avoid these)
- Assignment: "Write an episode … where a farmer interacts with two men …" → Exemplar: "MOENTJES, Clapperman. SPIEGELS, Sweeper. ANTJE, Child. A Farmer." [INVALID: list, not narrative]
- Assignment: "Compose a scene … showing how a child reacts …" → Exemplar: "The scene takes place in Maastricht." [INVALID: bare setting line]
- Assignment: "Draft a monologue … where Antje reveals her feelings …" → Exemplar: unrelated lines with no clear monologue by Antje [INVALID: mismatch with requested speaker/mode]

Positive examples (target shape)
- Assignment: "Compose a dialogue, in the style of '{book_title}' by {book_author}, between Antje and Spiegels as they discuss his proposal."
  Exemplar: a contiguous dialogue passage where Antje and Spiegels both speak about the proposal.
- Assignment: "Create a descriptive passage, in the style of '{book_title}' by {book_author}, capturing Antje’s solitude after the guests depart."
  Exemplar: a multi-sentence interior/narrative description of Antje alone.

Output schema
- Return a list of items with fields:
  - assignment: imperative writing instruction in the Text’s language; must include "{book_title}" and {book_author}".
  - exemplar: verbatim excerpt from the Text, ≤ 1024 chars, contiguous span.
  - start_char: 0-based start index in Text.
  - end_char: 0-based end index (exclusive).

Self-audit before returning (must pass all)
- The exemplar equals Text[start_char:end_char].
- 300 ≤ len(exemplar) ≤ 1024 (prefer ≥ 300 when coherent).
- The assignment is imperative (no question marks) and includes the exact title and author.
- The exemplar is not a list, not a heading, not a bare setting line.
- The exemplar contains narrative sentences and/or dialogue.
- The exemplar includes the actors/mode requested by the assignment (dialogue speakers, monologue speaker, or descriptive content of the specified setting/mood).
- No duplicate exemplars.
        """, str))

