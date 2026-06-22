from psalm.models.state import ArgumentationState, DeliberationState
from psalm.models.result import ArgumentationLog


def test_argumentation_state_defaults():
    state = ArgumentationState(
        source_text="Source text here.",
        target_text="Target text here.",
        dimensions=["character"],
        max_rounds=5,
    )
    assert state.current_round == 0
    assert state.arguments == []
    assert state.counter_arguments == []
    assert state.cross_examination_triggered is False
    assert state.stability_detected is False


def test_deliberation_state_defaults():
    arg_log = ArgumentationLog(rounds=[])
    state = DeliberationState(
        argumentation_log=arg_log,
        max_rounds=5,
    )
    assert state.current_round == 0
    assert state.discussion_messages == []
    assert state.vote_history == []
    assert state.consensus_reached is False
    assert state.final_verdict is None
    assert state.voting_strategy_applied is None
