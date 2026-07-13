import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import StageView from "./StageView";

describe("StageView", () => {
  it("shows a waiting message with no dimension selected", () => {
    render(<StageView dimension={null} />);
    expect(screen.getByText(/waiting for the trial to begin/i)).toBeInTheDocument();
  });

  it("shows the current phase and round", () => {
    render(<StageView dimension={makeDimensionState({ phase: "argumentation", currentRound: 2 })} />);
    expect(screen.getByText(/Argumentation — round 2/)).toBeInTheDocument();
  });

  it("shows the prosecutor's speech bubble when they are speaking", () => {
    render(
      <StageView dimension={makeDimensionState({ speakingRole: "prosecution", latestSpeech: "The scar matches." })} />,
    );
    expect(screen.getByText('"The scar matches."')).toBeInTheDocument();
  });

  it("does not show a speech bubble for the side that is not currently speaking", () => {
    render(
      <StageView dimension={makeDimensionState({ speakingRole: "prosecution", latestSpeech: "The scar matches." })} />,
    );
    const defensePodium = screen.getByTestId("stage-podium-defense");
    expect(defensePodium.textContent).not.toContain("The scar matches.");
  });

  it("tallies juror votes", () => {
    const dimension = makeDimensionState({
      jurorVotes: {
        "juror-0": { vote: "Guilty", rationale: "r", dimensionScores: [] },
        "juror-1": { vote: "Guilty", rationale: "r", dimensionScores: [] },
        "juror-2": { vote: "Not Guilty", rationale: "r", dimensionScores: [] },
      },
    });
    render(<StageView dimension={dimension} />);
    expect(screen.getByText("2 × Guilty")).toBeInTheDocument();
    expect(screen.getByText("1 × Not Guilty")).toBeInTheDocument();
  });

  it("shows the verdict once reached", () => {
    render(<StageView dimension={makeDimensionState({ phase: "verdict", verdict: "Guilty" })} />);
    expect(screen.getByText("Verdict: Guilty")).toBeInTheDocument();
  });
});
