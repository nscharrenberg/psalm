from __future__ import annotations
from psalm.agents.base import BaseAgent
from psalm.exceptions import PSALMAgentError
from psalm.models.config import AgentConfig
from psalm.models.result import ArgumentationLog, JurorVote


_SYSTEM_PROMPT = """\
You are a juror in a copyright infringement case governed by EU copyright law.
Review the argumentation logs and ongoing deliberation, then cast your vote.
Consider: (1) whether substantial similarity of protected creative expression was demonstrated,
(2) the strength of the prosecution's arguments vs. the defense's counter-arguments,
(3) the quality and relevance of the proofs (verbatim excerpts) provided.
Return your vote as one of: "Guilty", "Not Guilty", or "Undecided".
Provide a clear rationale for your decision.
"""


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
        rounds_text = "\n".join(
            f"Round {r.round}: {len(r.arguments)} prosecution arguments, "
            f"{len(r.counter_arguments)} defense counter-arguments"
            for r in argumentation_log.rounds
        )
        discussion_text = "\n".join(
            f"{m.get('role', 'juror')}: {m.get('content', '')}"
            for m in discussion_messages
        ) if discussion_messages else "No prior discussion."
        prompt = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Argumentation summary:\n{rounds_text}\n\n"
                    f"Deliberation so far:\n{discussion_text}\n\n"
                    f"You are juror {self._juror_id}. Cast your vote."
                ),
            },
        ]
        try:
            result = await self._call_structured(structured_llm, prompt)
            # Always stamp the vote with this juror's ID
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
