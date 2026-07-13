import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { PSALMEvent } from "../api/types";
import { useTrialStore } from "../state/store";
import LiveTrialPage from "./LiveTrialPage";

function renderAtTrial(trialId: string) {
  return render(
    <MemoryRouter initialEntries={[`/trial/${trialId}`]}>
      <Routes>
        <Route path="/trial/:trialId" element={<LiveTrialPage />} />
        <Route path="/trial/:trialId/result" element={<div>RESULT PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LiveTrialPage", () => {
  beforeEach(() => {
    useTrialStore.getState().reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts a live stream for the trial id in the URL", () => {
    const openSpy = vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    renderAtTrial("abc123");
    expect(openSpy).toHaveBeenCalledWith("abc123", expect.any(Function), expect.any(Function));
  });

  it("defaults to the Stage view", () => {
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    renderAtTrial("abc123");
    expect(screen.getByText("Stage")).toHaveClass("active");
  });

  it("switching tabs changes the active view", () => {
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    renderAtTrial("abc123");
    act(() => {
      screen.getByText("Transcript").click();
    });
    expect(screen.getByText("Transcript")).toHaveClass("active");
  });

  it("shows a dimension selector only once 2+ dimensions are running", () => {
    let onEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, cb) => {
      onEvent = cb;
      return () => {};
    });
    renderAtTrial("abc123");
    expect(screen.queryByRole("button", { name: "Character" })).not.toBeInTheDocument();

    act(() => {
      onEvent?.({
        event_id: "1", sequence: 1, timestamp: "t", run_id: "r", dimension: "Character",
        category: "lifecycle", type: "dimension_started", dimension_type: "infringement", importance: "high",
      } as PSALMEvent);
      onEvent?.({
        event_id: "2", sequence: 2, timestamp: "t", run_id: "r", dimension: "Plot",
        category: "lifecycle", type: "dimension_started", dimension_type: "infringement", importance: "high",
      } as PSALMEvent);
    });

    expect(screen.getByRole("button", { name: "Character" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Plot" })).toBeInTheDocument();
  });

  it("navigates to the results page once the trial is done", async () => {
    let onEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, cb) => {
      onEvent = cb;
      return () => {};
    });
    renderAtTrial("abc123");

    act(() => {
      onEvent?.({
        event_id: "1", sequence: 1, timestamp: "t", run_id: "r", dimension: null,
        category: "verdict", type: "final_verdict_reached",
        result: {
          verdict: "Guilty", rationale: "r", dimension_verdicts: [],
          metadata: {
            duration_seconds: 1, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
            voting_strategy_applied: "unanimous", agent_failures: [],
          },
        },
      } as PSALMEvent);
    });

    expect(await screen.findByText("RESULT PAGE")).toBeInTheDocument();
  });
});
