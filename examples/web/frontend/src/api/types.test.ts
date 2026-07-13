import { describe, expect, it } from "vitest";
import type { PSALMEvent, RunStarted, FinalVerdictReached } from "./types";

function narrowByType(event: PSALMEvent): string {
  // Exercises that TypeScript can discriminate the union purely on `.type`,
  // and that every member is actually reachable from the union type.
  switch (event.type) {
    case "run_started":
      return `dimensions:${event.dimensions.length}`;
    case "final_verdict_reached":
      return `verdict:${event.result.verdict}`;
    default:
      return event.type;
  }
}

describe("PSALMEvent discriminated union", () => {
  it("narrows RunStarted correctly by its literal type", () => {
    const event: RunStarted = {
      event_id: "1", sequence: 1, timestamp: "2026-01-01T00:00:00Z", run_id: "r1", dimension: null,
      category: "lifecycle", type: "run_started",
      dimensions: ["Character", "Plot"], evaluation_strategy: "fully_separate",
      source_length: 10, target_length: 12,
    };
    expect(narrowByType(event)).toBe("dimensions:2");
  });

  it("narrows FinalVerdictReached correctly by its literal type", () => {
    const event: FinalVerdictReached = {
      event_id: "2", sequence: 2, timestamp: "2026-01-01T00:00:01Z", run_id: "r1", dimension: null,
      category: "verdict", type: "final_verdict_reached",
      result: {
        verdict: "Guilty", rationale: "Because.", dimension_verdicts: [],
        metadata: {
          duration_seconds: 1, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
          voting_strategy_applied: "unanimous", agent_failures: [],
        },
      },
    };
    expect(narrowByType(event)).toBe("verdict:Guilty");
  });
});
