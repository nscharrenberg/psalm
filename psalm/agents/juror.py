from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent, _RunExecution
from psalm.dimensions.base import Dimension
from psalm.exceptions import PSALMAgentError
from psalm.models.config import AgentConfig
from psalm.models.result import ArgumentationLog, JurorVote

_VOTE_SYSTEM_PROMPT = """\
You are a juror in a copyright infringement case governed by EU copyright law.
Evaluate the arguments and counter-arguments presented by the prosecution and defense attorneys.
You are a lay evaluator — the attorneys handle legal doctrine; your job is to weigh argument
quality.

The prosecution carries the burden of proof. Ask:
- Did the prosecution present concrete, specific textual similarities?
- Did the defense successfully challenge those arguments (showing they are generic, coincidental,
  or legally insufficient)?
- Which side made stronger, more evidence-grounded arguments?

Weigh the EVIDENCE itself, not just the labels attorneys attach to it:
- Near-verbatim or word-for-word identical wording across a substantial passage (more than a
  handful of words) is direct, strong evidence of expression-level copying. Coincidental
  independent creation of long identical wording is not plausible — score such sub-dimensions
  "clear" unless the defense presents genuine evidence of independent creation, not merely a label.
- A single differing detail (a renamed character, one added phrase or clause) inside an otherwise
  identical or near-identical passage does not make the whole passage distinct. It means that one
  detail differs; the surrounding identical wording remains evidence of copying.
- Reserve "possible" for cases where the wording itself genuinely differs in substantial ways, not
  merely for the presence of any defense rebuttal.

For each sub-dimension you evaluate, apply this RUBRIC — a pure measure of textual/expression
similarity, not a legal conclusion:

| Score  | Label    | Meaning |
|--------|----------|---------|
| none   | No similarity | No meaningful textual/expression similarity found |
| generic | Slight similarity | Only isolated common words or phrasing; not a meaningful shared passage |
| possible | Possible independent creation | The wording itself differs substantially;
independent, coincidental creation is genuinely plausible |
| clear  | Clear similarity | Near-verbatim or identical wording in a substantial passage;
independent creation is not a plausible explanation |

You MUST fill in a DimensionScore for every sub-dimension you are asked to evaluate.

Work in this order: score every sub-dimension first, with reasoning grounded in the evidence
above. Then write your overall rationale, synthesizing those scores. Only after that, cast your
vote — it should follow from the rationale you just wrote, not precede it.

If you have voted in a prior deliberation round, maintain your position unless a fellow juror
made a specific, compelling argument that changes your view — and explain exactly what
persuaded you.
Vote options: "Guilty", "Not Guilty", or "Undecided".
"""

_DISCUSS_SYSTEM_PROMPT = """\
You are a juror in a copyright infringement case deliberating with fellow jurors.
Evaluate the quality of the arguments presented by the prosecution and defense.

The prosecution carries the burden of proof. Consider:
- Did the prosecution present specific, concrete textual similarities?
- Did the defense successfully challenge or rebut those arguments?
- Which side's reasoning was stronger and more grounded in the actual text?
- Be skeptical of any claim of distinctness that isn't backed by actually differing wording —
  identical or near-identical passages are strong evidence regardless of how the defense frames
  them, and a single differing detail does not launder an otherwise identical passage into a
  distinct one.

If you voted in a prior round, state your position and either argue for it using specific evidence
from the log, or explain what argument would change your mind.
If you are in the majority, present your strongest argument to persuade the minority.
If you are in the minority (or Undecided), explain what specific evidence would change your vote.
Be concise — 1-3 sentences. This is group deliberation, not a speech.
"""


class _DiscussionMessage(BaseModel):
    message: str


def _format_argument_section(
    parts: list[str], header: str, arguments: list, closing_statement: str | None
) -> None:
    parts.append(header)
    for i, arg in enumerate(arguments, 1):
        parts.append(f"  {i}. [{arg.dimension}] {arg.claim}")
        for p in arg.proofs:
            parts.append(f'     Source: "{p.source_excerpt}"')
            parts.append(f'     Target: "{p.target_excerpt}"')
            parts.append(f"     Relevance: {p.relevance}")
    if closing_statement:
        parts.append(f"  CLOSING STATEMENT: {closing_statement}")


def _format_argumentation_log(argumentation_log: ArgumentationLog) -> str:
    # Rejected arguments are audit-only (Judge discarded them as fabricated) — never shown here.
    parts: list[str] = []
    for r in argumentation_log.rounds:
        parts.append(f"=== Argumentation Round {r.round} ===")
        _format_argument_section(
            parts,
            "PROSECUTION ARGUMENTS:",
            r.prosecution_arguments,
            r.prosecution_closing_statement,
        )
        _format_argument_section(
            parts,
            "DEFENSE COUNTERS TO PROSECUTION:",
            r.defense_counters,
            r.defense_counter_closing_statement,
        )
        _format_argument_section(
            parts,
            "DEFENSE AFFIRMATIVE ARGUMENTS:",
            r.defense_arguments,
            r.defense_closing_statement,
        )
        _format_argument_section(
            parts,
            "PROSECUTION COUNTERS TO DEFENSE:",
            r.prosecution_counters,
            r.prosecution_counter_closing_statement,
        )
    if argumentation_log.prosecution_closing_argument or argumentation_log.defense_closing_argument:
        parts.append("=== Closing Arguments ===")
        if argumentation_log.prosecution_closing_argument:
            parts.append(
                f"PROSECUTION CLOSING ARGUMENT: {argumentation_log.prosecution_closing_argument}"
            )
        if argumentation_log.defense_closing_argument:
            parts.append(
                f"DEFENSE CLOSING ARGUMENT: {argumentation_log.defense_closing_argument}"
            )
    return "\n".join(parts)


def _format_prior_rounds(previous_rounds: list[dict], my_juror_id: str) -> str:
    if not previous_rounds:
        return "No prior deliberation rounds."
    parts: list[str] = []
    for rec in previous_rounds:
        round_num = rec.get("round")
        parts.append(f"--- Deliberation Round {round_num} ---")
        discussion = rec.get("discussion_messages", [])
        if discussion:
            parts.append("Discussion:")
            for msg in discussion:
                jid = msg.get("juror_id", "?")
                marker = " (YOU)" if jid == my_juror_id else ""
                parts.append(f"  {jid}{marker}: {msg.get('message', '')}")
        parts.append("Votes cast:")
        for v in rec.get("votes", []):
            jid = v.get("juror_id", "?")
            marker = " (YOUR PRIOR VOTE)" if jid == my_juror_id else ""
            parts.append(f"  {jid}{marker}: {v.get('vote', '?')} — {v.get('rationale', '')}")
    return "\n".join(parts)


def _format_sub_dimension_rubric(dimension: Dimension) -> str:
    lines = [f"Dimension: {dimension.name} — {dimension.description}"]
    if dimension.dimension_type == "exception":
        lines.append(
            "This is an EXCEPTION dimension, not an infringement dimension: you are not "
            "deciding whether the target text infringes copyright here. You are deciding "
            "whether this specific legal exception applies to the shared content. Vote "
            "\"Guilty\" if the exception applies, \"Not Guilty\" if it does not."
        )
    lines.append("Sub-dimensions to score:")
    for sd in dimension.sub_dimensions:
        lines.append(f"  [{sd.importance.value.upper()}] {sd.name}: {sd.description}")
    return "\n".join(lines)


class Juror(BaseAgent):
    def __init__(self, config: AgentConfig, juror_id: str, execution: _RunExecution) -> None:
        super().__init__(config, execution)
        self._juror_id = juror_id

    @property
    def role(self) -> str:
        return "juror"

    @property
    def juror_id(self) -> str:
        return self._juror_id

    async def deliberate(
        self,
        argumentation_log: ArgumentationLog,
        discussion_messages: list[dict[str, str]],
    ) -> JurorVote:
        structured_llm = self._llm.with_structured_output(JurorVote)
        log_text = _format_argumentation_log(argumentation_log)
        discussion_text = "\n".join(
            f"{m.get('role', 'juror')}: {m.get('content', '')}"
            for m in discussion_messages
        ) if discussion_messages else "No prior discussion."
        prompt = [
            {"role": "system", "content": _VOTE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"ARGUMENTATION LOG:\n{log_text}\n\n"
                    f"Deliberation so far:\n{discussion_text}\n\n"
                    f"You are juror {self._juror_id}. Cast your vote."
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return JurorVote(
                juror_id=self._juror_id,
                vote=result.vote,
                rationale=result.rationale,
            )
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Juror failed to cast a vote.",
                context={"role": self.role, "juror_id": self._juror_id},
                suggestion="Check LLM supports structured output.",
                cause=exc,
            ) from exc

    async def discuss(
        self,
        argumentation_log: ArgumentationLog,
        previous_rounds: list[dict],
        current_discussion: list[dict[str, str]],
        round: int,
    ) -> str:
        structured_llm = self._llm.with_structured_output(_DiscussionMessage)
        log_text = _format_argumentation_log(argumentation_log)
        prior_text = _format_prior_rounds(previous_rounds, self._juror_id)
        discussion_text = "\n".join(
            f"{m.get('juror_id', 'juror')}: {m.get('message', '')}"
            for m in current_discussion
        ) if current_discussion else "No discussion yet in this round."
        prompt = [
            {"role": "system", "content": _DISCUSS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"ARGUMENTATION LOG:\n{log_text}\n\n"
                    f"PRIOR DELIBERATION ROUNDS:\n{prior_text}\n\n"
                    f"CURRENT ROUND {round} DISCUSSION SO FAR:\n{discussion_text}\n\n"
                    f"You are juror {self._juror_id}. Share your view in 1-3 sentences, "
                    f"referencing specific arguments or proofs from the log above."
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return result.message
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Juror failed to generate discussion message.",
                context={"role": self.role, "juror_id": self._juror_id, "round": round},
                suggestion="Check LLM supports structured output.",
                cause=exc,
            ) from exc

    async def vote(
        self,
        argumentation_log: ArgumentationLog,
        previous_rounds: list[dict],
        discussion_messages: list[dict[str, str]],
        round: int,
        dimension: Dimension,
    ) -> JurorVote:
        structured_llm = self._llm.with_structured_output(JurorVote)
        log_text = _format_argumentation_log(argumentation_log)
        prior_text = _format_prior_rounds(previous_rounds, self._juror_id)
        discussion_text = "\n".join(
            f"{m.get('juror_id', 'juror')}: {m.get('message', '')}"
            for m in discussion_messages
        ) if discussion_messages else "No discussion yet."
        sub_dim_block = _format_sub_dimension_rubric(dimension)
        prompt = [
            {"role": "system", "content": _VOTE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"ARGUMENTATION LOG:\n{log_text}\n\n"
                    f"PRIOR DELIBERATION ROUNDS (including your previous votes and rationales):\n"
                    f"{prior_text}\n\n"
                    f"CURRENT ROUND {round} DISCUSSION:\n{discussion_text}\n\n"
                    f"DIMENSION TO EVALUATE:\n{sub_dim_block}\n\n"
                    f"You are juror {self._juror_id}. Cast your vote and fill in a DimensionScore "
                    f"for every sub-dimension listed above. Ground your rationale in the specific "
                    f"arguments and proofs. If changing your prior vote, explain what "
                    f"persuaded you."
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            return JurorVote(
                juror_id=self._juror_id,
                vote=result.vote,
                rationale=result.rationale,
                dimension_scores=result.dimension_scores,
            )
        except PSALMAgentError:
            raise
        except Exception as exc:
            raise PSALMAgentError(
                code="PSALM-A002",
                message="Juror failed to cast a vote.",
                context={"role": self.role, "juror_id": self._juror_id},
                suggestion="Check LLM supports structured output.",
                cause=exc,
            ) from exc

    async def vote_all_dimensions(
        self,
        argumentation_log: ArgumentationLog,
        previous_rounds: list[dict],
        discussion_messages: list[dict[str, str]],
        round: int,
        dimensions: list[Dimension],
    ) -> list[JurorVote]:
        """SHARED_ALL: produce one JurorVote per dimension in a single pass."""
        results = []
        for dim in dimensions:
            vote = await self.vote(
                argumentation_log=argumentation_log,
                previous_rounds=previous_rounds,
                discussion_messages=discussion_messages,
                round=round,
                dimension=dim,
            )
            results.append(vote.model_copy(update={"dimension": dim.name}))
        return results
