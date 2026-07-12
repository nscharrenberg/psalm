from psalm.dimensions import CHARACTER
from psalm.models.result import ArgumentationLog
from psalm.models.state import ArgumentationState, DeliberationState


def test_argumentation_state_defaults():
    state = ArgumentationState(
        source_text="Source text here.",
        target_text="Target text here.",
        dimensions=[CHARACTER],
        max_rounds=5,
    )
    assert state.current_round == 0
    assert state.prosecution_arguments == []
    assert state.defense_counters == []
    assert state.defense_arguments == []
    assert state.prosecution_counters == []
    assert state.stability_detected is False


def test_deliberation_state_defaults():
    arg_log = ArgumentationLog(rounds=[])
    state = DeliberationState(
        argumentation_log=arg_log,
        max_rounds=5,
        current_dimension=CHARACTER,
    )
    assert state.current_round == 0
    assert state.discussion_messages == []
    assert state.vote_history == []
    assert state.consensus_reached is False
    assert state.final_verdict is None
    assert state.voting_strategy_applied is None


def test_deliberation_state_new_fields_default():
    arg_log = ArgumentationLog(rounds=[])
    state = DeliberationState(
        argumentation_log=arg_log,
        max_rounds=3,
        current_dimension=CHARACTER,
    )
    assert state.current_round_votes == []
    assert state.debate_log is None


def test_deliberation_state_accepts_debate_log():
    arg_log = ArgumentationLog(rounds=[])
    state = DeliberationState(
        argumentation_log=arg_log,
        max_rounds=3,
        current_dimension=CHARACTER,
        debate_log={"rounds": [], "final_voting_strategy_applied": "unanimous"},
    )
    assert state.debate_log is not None
    assert state.debate_log["final_voting_strategy_applied"] == "unanimous"


def test_argumentation_state_accepts_dimension_objects():
    state = ArgumentationState(
        source_text="source",
        target_text="target",
        dimensions=[CHARACTER],
        max_rounds=3,
    )
    assert len(state.dimensions) == 1
    assert state.dimensions[0].name == "Character"


def test_argumentation_state_has_four_step_fields():
    state = ArgumentationState(
        source_text="src", target_text="tgt", dimensions=[CHARACTER], max_rounds=3
    )
    # Step 1
    assert state.pending_prosecution_arguments == []
    assert state.validated_prosecution_arguments == []
    assert state.prosecution_arguments == []
    # Step 2
    assert state.pending_defense_counters == []
    assert state.defense_counters == []
    # Step 3
    assert state.pending_defense_arguments == []
    assert state.validated_defense_arguments == []
    assert state.defense_arguments == []
    # Step 4
    assert state.pending_prosecution_counters == []
    assert state.prosecution_counters == []


def test_argumentation_state_old_fields_removed():
    state = ArgumentationState(
        source_text="src", target_text="tgt", dimensions=[CHARACTER], max_rounds=3
    )
    assert not hasattr(state, "arguments")
    assert not hasattr(state, "counter_arguments")
    assert not hasattr(state, "cross_examination_triggered")


def test_deliberation_state_has_current_dimension(minimal_argumentation_log):
    state = DeliberationState(
        argumentation_log=minimal_argumentation_log,
        max_rounds=2,
        current_dimension=CHARACTER,
    )
    assert state.current_dimension.name == "Character"


def test_deliberation_state_weighted_score_defaults_to_zero(minimal_argumentation_log):
    state = DeliberationState(
        argumentation_log=minimal_argumentation_log,
        max_rounds=2,
        current_dimension=CHARACTER,
    )
    assert state.weighted_score == 0.0


def test_argumentation_state_has_closing_statement_accumulators():
    state = ArgumentationState(
        source_text="src", target_text="tgt", dimensions=[CHARACTER], max_rounds=3
    )
    assert state.prosecution_closing_statements == []
    assert state.defense_counter_closing_statements == []
    assert state.defense_closing_statements == []
    assert state.prosecution_counter_closing_statements == []


def test_argumentation_state_has_rejected_argument_accumulators():
    state = ArgumentationState(
        source_text="src", target_text="tgt", dimensions=[CHARACTER], max_rounds=3
    )
    assert state.prosecution_rejected_arguments == []
    assert state.defense_counter_rejected_arguments == []
    assert state.defense_rejected_arguments == []
    assert state.prosecution_counter_rejected_arguments == []


def test_argumentation_state_has_closing_argument_fields():
    state = ArgumentationState(
        source_text="src", target_text="tgt", dimensions=[CHARACTER], max_rounds=3
    )
    assert state.prosecution_closing_argument is None
    assert state.defense_closing_argument is None
