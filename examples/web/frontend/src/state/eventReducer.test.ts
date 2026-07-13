import { describe, expect, it } from "vitest";
import type {
  ArgumentSubmitted,
  DimensionStarted,
  DimensionVerdictReached,
  FinalVerdictReached,
  JurorVoteCast,
  RunFailed,
  RunStarted,
} from "../api/types";
import { applyEvent, createInitialState } from "./eventReducer";

function envelope(overrides: Partial<{
  event_id: string; sequence: number; timestamp: string; run_id: string; dimension: string | null;
}> = {}) {
  return {
    event_id: "e1", sequence: 1, timestamp: "2026-01-01T00:00:00Z", run_id: "r1", dimension: null,
    ...overrides,
  };
}

describe("applyEvent", () => {
  it("run_started marks the trial running and records the run id", () => {
    const event: RunStarted = {
      ...envelope(), category: "lifecycle", type: "run_started",
      dimensions: ["Character"], evaluation_strategy: "fully_separate", source_length: 5, target_length: 6,
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.status).toBe("running");
    expect(state.runId).toBe("r1");
    expect(state.evaluationStrategy).toBe("fully_separate");
  });

  it("run_failed marks the trial in an error state with the message", () => {
    const event: RunFailed = {
      ...envelope(), category: "lifecycle", type: "run_failed",
      code: "PSALM-A003", message: "LLM retry limit reached.", context: {},
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.status).toBe("error");
    expect(state.errorMessage).toBe("LLM retry limit reached.");
  });

  it("dimension_started creates a new dimension entry", () => {
    const event: DimensionStarted = {
      ...envelope({ dimension: "Character" }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.dimensionOrder).toEqual(["Character"]);
    expect(state.dimensions["Character"].dimensionType).toBe("infringement");
    expect(state.dimensions["Character"].status).toBe("running");
  });

  it("dimension_started with a null dimension is ignored rather than crashing", () => {
    const event: DimensionStarted = {
      ...envelope({ dimension: null }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.dimensionOrder).toEqual([]);
  });

  it("argument_submitted appends a transcript entry to the right dimension and tracks the speaker", () => {
    let state = applyEvent(createInitialState(), {
      ...envelope({ dimension: "Character" }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    } as DimensionStarted);
    const event: ArgumentSubmitted = {
      ...envelope({ dimension: "Character", event_id: "e2" }), category: "argumentation", type: "argument_submitted",
      round: 1, role: "prosecution", kind: "argument",
      argument: { claim: "The scar matches.", dimension: "Character", proofs: [], agent_role: "prosecutor", round: 1 },
    };
    state = applyEvent(state, event);
    expect(state.dimensions["Character"].transcript).toHaveLength(1);
    expect(state.dimensions["Character"].transcript[0].text).toContain("The scar matches.");
    expect(state.dimensions["Character"].speakingRole).toBe("prosecution");
  });

  it("argument_submitted with a null dimension goes to the shared transcript", () => {
    const event: ArgumentSubmitted = {
      ...envelope({ dimension: null }), category: "argumentation", type: "argument_submitted",
      round: 1, role: "prosecution", kind: "argument",
      argument: { claim: "Shared claim.", dimension: "Character", proofs: [], agent_role: "prosecutor", round: 1 },
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.sharedTranscript).toHaveLength(1);
    expect(state.dimensions).toEqual({});
  });

  it("juror_vote_cast records the vote under the right dimension", () => {
    let state = applyEvent(createInitialState(), {
      ...envelope({ dimension: "Character" }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    } as DimensionStarted);
    const event: JurorVoteCast = {
      ...envelope({ dimension: "Character" }), category: "deliberation", type: "juror_vote_cast",
      round: 1, juror_id: "juror-0", vote: "Guilty", rationale: "Strong evidence.", dimension_scores: [],
    };
    state = applyEvent(state, event);
    expect(state.dimensions["Character"].jurorVotes["juror-0"]).toEqual({
      vote: "Guilty", rationale: "Strong evidence.", dimensionScores: [],
    });
  });

  it("dimension_verdict_reached marks that dimension done with its verdict", () => {
    let state = applyEvent(createInitialState(), {
      ...envelope({ dimension: "Character" }), category: "lifecycle", type: "dimension_started",
      dimension_type: "infringement", importance: "high",
    } as DimensionStarted);
    const event: DimensionVerdictReached = {
      ...envelope({ dimension: "Character" }), category: "verdict", type: "dimension_verdict_reached",
      dimension_type: "infringement", importance: "high", verdict: "Guilty", weighted_score: 0.8,
    };
    state = applyEvent(state, event);
    expect(state.dimensions["Character"].status).toBe("done");
    expect(state.dimensions["Character"].verdict).toBe("Guilty");
    expect(state.dimensions["Character"].weightedScore).toBe(0.8);
  });

  it("final_verdict_reached marks the whole trial done and stores the result", () => {
    const event: FinalVerdictReached = {
      ...envelope(), category: "verdict", type: "final_verdict_reached",
      result: {
        verdict: "Guilty", rationale: "Because.", dimension_verdicts: [],
        metadata: {
          duration_seconds: 1, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
          voting_strategy_applied: "unanimous", agent_failures: [],
        },
      },
    };
    const state = applyEvent(createInitialState(), event);
    expect(state.status).toBe("done");
    expect(state.finalResult?.verdict).toBe("Guilty");
  });

  it("is a pure function — never mutates the input state", () => {
    const initial = createInitialState();
    const frozen = JSON.stringify(initial);
    applyEvent(initial, {
      ...envelope(), category: "lifecycle", type: "run_started",
      dimensions: ["Character"], evaluation_strategy: "fully_separate", source_length: 1, target_length: 1,
    } as RunStarted);
    expect(JSON.stringify(initial)).toBe(frozen);
  });
});
