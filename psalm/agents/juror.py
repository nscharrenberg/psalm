from __future__ import annotations

from pydantic import BaseModel

from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.config import AgentConfig
from psalm.models.result import ArgumentationLog, JurorVote

_VOTE_SYSTEM_PROMPT = """\
You are a juror in a copyright infringement case governed by EU copyright law.
Evaluate the arguments and counter-arguments presented by the prosecution and defense attorneys.
You are a lay evaluator — the attorneys handle legal doctrine; 
your job is to weigh argument quality.

The prosecution carries the burden of proof. Ask:
- Did the prosecution present concrete, specific textual similarities?
- Did the defense successfully challenge those arguments (showing they are generic, coincidental,
  or legally insufficient)?
- Which side made stronger, more evidence-grounded arguments?

If the defense has effectively rebutted the prosecution's claims, lean toward Not Guilty.
If the prosecution has demonstrated clear, specific similarities the defense could not credibly
refute, lean toward Guilty.

If you have voted in a prior deliberation round, maintain your position unless a fellow juror made
a specific, compelling argument that changes your view — and explain exactly what persuaded you.
Vote options: "Guilty", "Not Guilty", or "Undecided".
"""

_DISCUSS_SYSTEM_PROMPT = """\
You are a juror in a copyright infringement case deliberating with fellow jurors.
Evaluate the quality of the arguments presented by the prosecution and defense.

The prosecution carries the burden of proof. Consider:
- Did the prosecution present specific, concrete textual similarities?
- Did the defense successfully challenge or rebut those arguments?
- Which side's reasoning was stronger and more grounded in the actual text?

If you voted in a prior round, state your position and either argue for it using specific evidence
from the log, or explain what argument would change your mind.
If you are in the majority, present your strongest argument to persuade the minority.
If you are in the minority (or Undecided), explain what specific evidence would change your vote.
Be concise — 1-3 sentences. This is group deliberation, not a speech.
"""


class _DiscussionMessage(BaseModel):
    message: str


def _format_argumentation_log(argumentation_log: ArgumentationLog) -> str:
    parts: list[str] = []
    for r in argumentation_log.rounds:
        parts.append(f"=== Argumentation Round {r.round} ===")
        parts.append("PROSECUTION ARGUMENTS:")
        for i, arg in enumerate(r.arguments, 1):
            parts.append(f"  {i}. [{arg.dimension}] {arg.claim}")
            for p in arg.proofs:
                parts.append(f'     Source: "{p.source_excerpt}"')
                parts.append(f'     Target: "{p.target_excerpt}"')
                parts.append(f"     Relevance: {p.relevance}")
        parts.append("DEFENSE COUNTER-ARGUMENTS:")
        for i, arg in enumerate(r.counter_arguments, 1):
            parts.append(f"  {i}. [{arg.dimension}] {arg.claim}")
            for p in arg.proofs:
                parts.append(f'     Source: "{p.source_excerpt}"')
                parts.append(f'     Target: "{p.target_excerpt}"')
                parts.append(f"     Relevance: {p.relevance}")
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


class Juror(BaseAgent):
    def __init__(self, config: AgentConfig, juror_id: str) -> None:
        super().__init__(config)
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
    ) -> JurorVote:
        structured_llm = self._llm.with_structured_output(JurorVote)
        log_text = _format_argumentation_log(argumentation_log)
        prior_text = _format_prior_rounds(previous_rounds, self._juror_id)
        discussion_text = "\n".join(
            f"{m.get('juror_id', 'juror')}: {m.get('message', '')}"
            for m in discussion_messages
        ) if discussion_messages else "No discussion."
        prompt = [
            {"role": "system", "content": _VOTE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"ARGUMENTATION LOG:\n{log_text}\n\n"
                    f"PRIOR DELIBERATION ROUNDS (including your previous votes and rationales):\n"
                    f"{prior_text}\n\n"
                    f"CURRENT ROUND {round} DISCUSSION:\n{discussion_text}\n\n"
                    f"You are juror {self._juror_id}. Cast your vote, grounding your rationale "
                    f"in the specific arguments and proofs above. If you are changing your prior "
                    f"vote, explain exactly what persuaded you."
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
