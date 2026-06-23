from __future__ import annotations

from pydantic import BaseModel

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

_VOTE_SYSTEM_PROMPT = """\
You are a juror in a copyright infringement case governed by EU copyright law.
Review the argumentation logs and ongoing deliberation, then cast your vote.
Consider: (1) whether substantial similarity of protected creative expression was demonstrated,
(2) the strength of the prosecution's arguments vs. the defense's counter-arguments,
(3) the quality and relevance of the proofs (verbatim excerpts) provided.
Return your vote as one of: "Guilty", "Not Guilty", or "Undecided".
Provide a clear rationale for your decision.
"""

_DISCUSS_SYSTEM_PROMPT = """\
You are a juror in a copyright infringement case discussing your views with fellow jurors.
Review the evidence and prior discussion, then share your perspective in 1-2 sentences.
Focus on the most compelling aspect of the case from your perspective.
Be concise — you are contributing to a group deliberation, not delivering a speech.
"""


class _DiscussionMessage(BaseModel):
    message: str


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

    async def discuss(
        self,
        argumentation_log: ArgumentationLog,
        previous_rounds: list[dict],
        current_discussion: list[dict[str, str]],
        round: int,
    ) -> str:
        structured_llm = self._llm.with_structured_output(_DiscussionMessage)
        rounds_text = "\n".join(
            f"Round {r.round}: {len(r.arguments)} prosecution arguments, "
            f"{len(r.counter_arguments)} defense counter-arguments"
            for r in argumentation_log.rounds
        )
        prior_votes_text = "\n".join(
            f"Round {rec.get('round')}: {[v.get('vote') for v in rec.get('votes', [])]}"
            for rec in previous_rounds
        ) if previous_rounds else "No prior rounds."
        discussion_text = "\n".join(
            f"{m.get('juror_id', 'juror')}: {m.get('message', '')}"
            for m in current_discussion
        ) if current_discussion else "No discussion yet."
        prompt = [
            {"role": "system", "content": _DISCUSS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Argumentation summary:\n{rounds_text}\n\n"
                    f"Previous voting rounds:\n{prior_votes_text}\n\n"
                    f"Current discussion:\n{discussion_text}\n\n"
                    f"You are juror {self._juror_id} in deliberation round {round}. "
                    f"Share your view."
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
        rounds_text = "\n".join(
            f"Round {r.round}: {len(r.arguments)} prosecution arguments, "
            f"{len(r.counter_arguments)} defense counter-arguments"
            for r in argumentation_log.rounds
        )
        prior_votes_text = "\n".join(
            f"Round {rec.get('round')}: {[v.get('vote') for v in rec.get('votes', [])]}"
            for rec in previous_rounds
        ) if previous_rounds else "No prior rounds."
        discussion_text = "\n".join(
            f"{m.get('juror_id', 'juror')}: {m.get('message', '')}"
            for m in discussion_messages
        ) if discussion_messages else "No discussion."
        prompt = [
            {"role": "system", "content": _VOTE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Argumentation summary:\n{rounds_text}\n\n"
                    f"Previous voting rounds:\n{prior_votes_text}\n\n"
                    f"Deliberation discussion:\n{discussion_text}\n\n"
                    f"You are juror {self._juror_id} in voting round {round}. Cast your vote."
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
