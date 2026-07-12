# tests/conftest.py
import pytest

from psalm.models.config import AgentConfig, DebateConfig
from psalm.models.evidence import Argument, Proof
from psalm.models.result import (
    ArgumentationLog,
    DebateLog,
    DimensionVerdict,
    JurorVote,
    PSALMResult,
    ResultMetadata,
    RoundArguments,
    RoundDeliberation,
)


@pytest.fixture
def agent_config() -> AgentConfig:
    return AgentConfig(
        base_url="https://api.openai.com/v1",
        api_key="sk-test-key",
        model="gpt-4o",
        temperature=0.0,
        seed=42,
    )


@pytest.fixture
def debate_config() -> DebateConfig:
    return DebateConfig()


@pytest.fixture
def sample_proof() -> Proof:
    return Proof(
        source_excerpt="The wizard had bright blue eyes.",
        target_excerpt="The sorcerer possessed striking azure irises.",
        relevance="Both characters share a distinctive blue eye color trait.",
    )


@pytest.fixture
def sample_argument(sample_proof: Proof) -> Argument:
    return Argument(
        claim="Both characters share unique physical traits.",
        dimension="character",
        proofs=[sample_proof],
        agent_role="prosecutor",
        round=1,
    )


@pytest.fixture
def sample_counter_argument(sample_proof: Proof) -> Argument:
    return Argument(
        claim="Eye color is a generic trait not protected by copyright.",
        dimension="character",
        proofs=[sample_proof],
        agent_role="defense",
        round=1,
    )


@pytest.fixture
def minimal_argumentation_log(
    sample_argument: Argument, sample_counter_argument: Argument
) -> ArgumentationLog:
    return ArgumentationLog(
        rounds=[
            RoundArguments(
                round=1,
                prosecution_arguments=[sample_argument],
                defense_counters=[sample_counter_argument],
                defense_arguments=[],
                prosecution_counters=[],
            )
        ]
    )


@pytest.fixture
def minimal_debate_log() -> DebateLog:
    return DebateLog(
        rounds=[
            RoundDeliberation(
                round=1,
                discussion_messages=[
                    {"juror_id": "juror-0", "message": "Evidence supports infringement."}
                ],
                votes=[
                    JurorVote(juror_id="juror-0", vote="Guilty", rationale="Strong evidence.")
                ],
                aggregated_result="Guilty",
            )
        ],
        final_voting_strategy_applied="simple_majority",
    )


@pytest.fixture
def minimal_psalm_result(minimal_argumentation_log, minimal_debate_log) -> PSALMResult:
    from psalm.dimensions.base import Importance
    dv = DimensionVerdict(
        dimension="character",
        importance=Importance.HIGH,
        verdict="Guilty",
        weighted_score=0.8,
        argumentation_log=minimal_argumentation_log,
        debate_log=minimal_debate_log,
    )
    return PSALMResult(
        verdict="Guilty",
        rationale="The target text substantially reproduces protected character traits.",
        dimension_verdicts=[dv],
        metadata=ResultMetadata(
            duration_seconds=5.0,
            argumentation_rounds_used=1,
            deliberation_rounds_used=1,
            voting_strategy_applied="simple_majority",
        ),
    )


from contextlib import contextmanager

from psalm.events.base import EventSink
from psalm.events.context import _current_sink


@contextmanager
def bound_event_sink():
    """Bind a fresh EventSink to the ambient context for the duration of the block."""
    sink = EventSink(run_id="test-run")
    token = _current_sink.set(sink)
    try:
        yield sink
    finally:
        _current_sink.reset(token)


async def drain_events(sink: EventSink) -> list:
    events = []
    while not sink.empty():
        events.append(await sink.get())
    return events
