import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { PSALMEvent, TrialDetail } from "../api/types";
import { useTrialStore } from "../state/store";
import ResultsPage from "./ResultsPage";

const fakeDetail: TrialDetail = {
  id: "abc", created_at: "t", status: "done", source_text_preview: "s", target_text_preview: "t",
  verdict: "Guilty", error_message: null,
  config_summary: {},
  result: {
    verdict: "Guilty", rationale: "Strong evidence throughout.",
    dimension_verdicts: [
      {
        dimension: "Character", dimension_type: "infringement", importance: "high", verdict: "Guilty",
        weighted_score: 0.8,
        argumentation_log: { rounds: [], prosecution_closing_argument: null, defense_closing_argument: null },
        debate_log: { rounds: [], final_voting_strategy_applied: "unanimous" },
      },
    ],
    metadata: {
      duration_seconds: 5, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
      voting_strategy_applied: "unanimous", agent_failures: [],
    },
  },
};

function renderAtResult(trialId: string) {
  return render(
    <MemoryRouter initialEntries={[`/trial/${trialId}/result`]}>
      <Routes>
        <Route path="/trial/:trialId/result" element={<ResultsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ResultsPage", () => {
  beforeEach(() => {
    useTrialStore.getState().reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the verdict and rationale once loaded", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    renderAtResult("abc");
    expect(await screen.findByText("Verdict: Guilty")).toBeInTheDocument();
    expect(screen.getByText("Strong evidence throughout.")).toBeInTheDocument();
  });

  it("shows the per-dimension breakdown table", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");
    expect(screen.getByText("0.80")).toBeInTheDocument();
  });

  it("shows an error banner for a failed trial", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue({
      ...fakeDetail, status: "error", error_message: "LLM connection failed.", result: null,
    });
    renderAtResult("abc");
    expect(await screen.findByText(/Trial failed: LLM connection failed\./)).toBeInTheDocument();
  });

  it("shows a Replay button only when live events were buffered, and starts replay mode on click", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    useTrialStore.setState({ allEvents: [{ type: "run_started" } as PSALMEvent] });
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");

    const replayButton = screen.getByText("Replay this trial");
    act(() => {
      replayButton.click();
    });
    expect(screen.getByText("Replay")).toBeInTheDocument();
  });

  it("does not show a Replay button when no live events were buffered (e.g. loaded from history)", async () => {
    vi.spyOn(client, "getTrial").mockResolvedValue(fakeDetail);
    renderAtResult("abc");
    await screen.findByText("Verdict: Guilty");
    expect(screen.queryByText("Replay this trial")).not.toBeInTheDocument();
  });
});
