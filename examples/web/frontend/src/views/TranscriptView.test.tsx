import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import type { PSALMEvent } from "../api/types";
import TranscriptView from "./TranscriptView";

function withSequence(sequence: number): PSALMEvent {
  return { sequence } as PSALMEvent;
}

describe("TranscriptView", () => {
  it("shows a waiting message when there are no entries yet", () => {
    render(<TranscriptView dimension={null} sharedTranscript={[]} />);
    expect(screen.getByText(/waiting for the trial to begin/i)).toBeInTheDocument();
  });

  it("renders each transcript entry's text", () => {
    const dimension = makeDimensionState({
      transcript: [
        { id: "1", timestamp: "t", dimension: "Character", kind: "argument", role: "prosecution", text: "The scar matches.", raw: withSequence(1) },
        { id: "2", timestamp: "t", dimension: "Character", kind: "rejection", role: "prosecution", text: "Judge sustains an objection.", raw: withSequence(2) },
      ],
    });
    render(<TranscriptView dimension={dimension} sharedTranscript={[]} />);
    expect(screen.getByText("The scar matches.")).toBeInTheDocument();
    expect(screen.getByText("Judge sustains an objection.")).toBeInTheDocument();
  });

  it("merges and orders shared and dimension transcripts by sequence", () => {
    const shared = [
      { id: "s1", timestamp: "t", dimension: null, kind: "argument", text: "Shared first.", raw: withSequence(1) },
    ];
    const dimension = makeDimensionState({
      transcript: [
        { id: "d1", timestamp: "t", dimension: "Character", kind: "vote", text: "Then a vote.", raw: withSequence(2) },
      ],
    });
    render(<TranscriptView dimension={dimension} sharedTranscript={shared} />);
    const entries = screen.getAllByTestId("transcript-entry");
    expect(entries.map((el) => el.textContent)).toEqual(["Shared first.", "Then a vote."]);
  });
});
