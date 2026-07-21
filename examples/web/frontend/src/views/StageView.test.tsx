import { MantineProvider } from "@mantine/core";
import { describe, expect, it } from "vitest";
import { makeDimensionState } from "../state/testFixtures";
import { theme } from "../theme";
import StageView from "./StageView";
import { render, screen } from "../test/render";

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

  it("shows a juror's speech bubble in the jury area when they are speaking", () => {
    render(
      <StageView dimension={makeDimensionState({ speakingRole: "juror-1", latestSpeech: "I believe the evidence is clear." })} />,
    );
    const jury = screen.getByTestId("stage-jury");
    expect(jury.textContent).toContain("I believe the evidence is clear.");
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

  it("applies a pulse-highlight class to newly-arrived speech so updates are visually obvious", () => {
    render(
      <StageView dimension={makeDimensionState({ speakingRole: "prosecution", latestSpeech: "The scar matches." })} />,
    );
    expect(screen.getByText('"The scar matches."')).toHaveClass("stage-speech-pulse");
  });

  it("renders correctly when the same instance transitions from no dimension to a dimension (regression: was a conditional hook)", () => {
    const { rerender } = render(<StageView dimension={null} />);
    expect(screen.getByText(/waiting for the trial to begin/i)).toBeInTheDocument();

    // Re-wrap in the same MantineProvider so the rerender replaces StageView's
    // props in place (same component instance/fiber) rather than unmounting and
    // remounting a fresh instance under a different root element type — the
    // latter would mask the exact hooks-order bug this test guards against.
    rerender(
      <MantineProvider theme={theme} forceColorScheme="dark">
        <StageView dimension={makeDimensionState({ phase: "argumentation", currentRound: 1 })} />
      </MantineProvider>,
    );
    expect(screen.getByText(/Argumentation — round 1/)).toBeInTheDocument();
  });
});
