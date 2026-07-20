import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import type { PSALMEvent } from "../api/types";
import TimelineView from "./TimelineView";
import { render, screen } from "../test/render";

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
    // Steps are: 0 Setup, 1 Argumentation round 1, 2 Argumentation round 2, 3 Deliberation, 4 Verdict.
    expect(screen.getByTestId("timeline-step-2")).toHaveAttribute("data-status", "current");
    expect(screen.getByTestId("timeline-step-2")).toHaveTextContent("Argumentation round 2");
    expect(screen.getByTestId("timeline-step-1")).toHaveAttribute("data-status", "done");
    expect(screen.getByTestId("timeline-step-1")).toHaveTextContent("Argumentation round 1");
  });

  it("marks verdict as done once reached", () => {
    render(<TimelineView dimension={makeDimensionState({ phase: "verdict", currentRound: 2 })} sharedTranscript={[]} />);
    expect(screen.getByTestId("timeline-step-4")).toHaveAttribute("data-status", "done");
    expect(screen.getByTestId("timeline-step-4")).toHaveTextContent("Verdict");
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
