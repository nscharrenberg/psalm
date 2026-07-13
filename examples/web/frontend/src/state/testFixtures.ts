import type { DimensionState } from "./eventReducer";

export function makeDimensionState(overrides: Partial<DimensionState> = {}): DimensionState {
  return {
    name: "Character",
    dimensionType: "infringement",
    importance: "high",
    phase: "argumentation",
    currentRound: 1,
    status: "running",
    verdict: null,
    weightedScore: null,
    speakingRole: null,
    latestSpeech: null,
    jurorVotes: {},
    rejectedArgumentCount: 0,
    transcript: [],
    ...overrides,
  };
}
