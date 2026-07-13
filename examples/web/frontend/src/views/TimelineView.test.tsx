import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import type { PSALMEvent } from "../api/types";
import TimelineView from "./TimelineView";

function withSequence(sequence: number): PSALMEvent {
  return { sequence } as PSALMEvent;
}

describe("TimelineView", () => {
  it("shows a waiting message with no dimension selected", () => {
    render(<TimelineView dimension={null} sharedTranscript={[]} />);
    expect(screen.getByText(/waiting for the trial to begin/i)).toBeInTheDocument();
  });

  it("marks the current argumentation round as current and earlier rounds as done", () => {
    render(<TimelineView dimension={makeDimensionState({ phase: "argumentation", currentRound: 2 })} sharedTranscript={[]} />);
    expect(screen.getByText(/▶ Argumentation round 2/)).toBeInTheDocument();
    expect(screen.getByText(/✅ Argumentation round 1/)).toBeInTheDocument();
  });

  it("marks verdict as done once reached", () => {
    render(<TimelineView dimension={makeDimensionState({ phase: "verdict", currentRound: 2 })} sharedTranscript={[]} />);
    expect(screen.getByText(/✅ Verdict/)).toBeInTheDocument();
  });

  it("renders the merged transcript for the current phase", () => {
    const dimension = makeDimensionState({
      transcript: [
        { id: "1", timestamp: "t", dimension: "Character", kind: "argument", text: "The scar matches.", raw: withSequence(1) },
      ],
    });
    render(<TimelineView dimension={dimension} sharedTranscript={[]} />);
    expect(screen.getByText("The scar matches.")).toBeInTheDocument();
  });
});
