import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { FinalVerdictReached, PSALMEvent, RunStarted } from "../api/types";
import { useTrialStore } from "./store";

function makeRunStarted(overrides: Partial<RunStarted> = {}): RunStarted {
  return {
    event_id: "e1", sequence: 1, timestamp: "t", run_id: "r1", dimension: null,
    category: "lifecycle", type: "run_started",
    dimensions: ["Character"], evaluation_strategy: "fully_separate", source_length: 1, target_length: 1,
    ...overrides,
  };
}

function makeFinalVerdict(overrides: Partial<FinalVerdictReached> = {}): FinalVerdictReached {
  return {
    event_id: "e2", sequence: 2, timestamp: "t", run_id: "r1", dimension: null,
    category: "verdict", type: "final_verdict_reached",
    result: {
      verdict: "Guilty", rationale: "Because.", dimension_verdicts: [],
      metadata: {
        duration_seconds: 1, argumentation_rounds_used: 1, deliberation_rounds_used: 1,
        voting_strategy_applied: "unanimous", agent_failures: [],
      },
    },
    ...overrides,
  };
}

describe("useTrialStore", () => {
  beforeEach(() => {
    useTrialStore.getState().reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("startLive opens an event stream and applies incoming events", () => {
    let capturedOnEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, onEvent) => {
      capturedOnEvent = onEvent;
      return () => {};
    });

    useTrialStore.getState().startLive("trial-1");
    expect(useTrialStore.getState().mode).toBe("live");

    capturedOnEvent?.(makeRunStarted());
    expect(useTrialStore.getState().state.status).toBe("running");
    expect(useTrialStore.getState().allEvents).toHaveLength(1);
  });

  it("stopLive closes the underlying stream", () => {
    const close = vi.fn();
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(close);

    useTrialStore.getState().startLive("trial-1");
    useTrialStore.getState().stopLive();
    expect(close).toHaveBeenCalled();
  });

  it("loadForReplay resets state and stores the full event list", () => {
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);
    const s = useTrialStore.getState();
    expect(s.mode).toBe("replay");
    expect(s.allEvents).toHaveLength(2);
    expect(s.state.status).toBe("idle");
  });

  it("scrubTo recomputes state deterministically from the beginning", () => {
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);
    useTrialStore.getState().scrubTo(0);
    expect(useTrialStore.getState().state.status).toBe("running");
    expect(useTrialStore.getState().state.finalResult).toBeNull();

    useTrialStore.getState().scrubTo(1);
    expect(useTrialStore.getState().state.finalResult?.verdict).toBe("Guilty");
  });

  it("scrubTo clamps to the valid event range", () => {
    useTrialStore.getState().loadForReplay([makeRunStarted()]);
    useTrialStore.getState().scrubTo(99);
    expect(useTrialStore.getState().replayIndex).toBe(0);
  });

  it("play advances through events over time and stops at the end", () => {
    vi.useFakeTimers();
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);
    useTrialStore.getState().setReplaySpeed(1);
    useTrialStore.getState().play();
    expect(useTrialStore.getState().isPlaying).toBe(true);

    vi.advanceTimersByTime(2000);

    expect(useTrialStore.getState().isPlaying).toBe(false);
    expect(useTrialStore.getState().state.finalResult?.verdict).toBe("Guilty");
  });

  it("pause stops advancing", () => {
    vi.useFakeTimers();
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);
    useTrialStore.getState().play();
    useTrialStore.getState().pause();
    const indexAfterPause = useTrialStore.getState().replayIndex;

    vi.advanceTimersByTime(2000);

    expect(useTrialStore.getState().replayIndex).toBe(indexAfterPause);
    expect(useTrialStore.getState().isPlaying).toBe(false);
  });

  it("loadForReplay closes a still-open live stream so it cannot corrupt replay state", () => {
    const close = vi.fn();
    let capturedOnEvent: ((event: PSALMEvent) => void) | undefined;
    vi.spyOn(client, "openTrialEventStream").mockImplementation((_id, onEvent) => {
      capturedOnEvent = onEvent;
      return close;
    });

    useTrialStore.getState().startLive("trial-1");
    // Do NOT call stopLive()/reset() here — this is the scenario the bug covers:
    // entering replay mode while a live stream is technically still open.
    useTrialStore.getState().loadForReplay([makeRunStarted(), makeFinalVerdict()]);

    expect(close).toHaveBeenCalled();

    // Simulate the (now-closed, but still-referenced-by-old-closure) stream firing anyway
    // — this must NOT corrupt the replay snapshot.
    const stateBeforeStaleEvent = useTrialStore.getState().state;
    capturedOnEvent?.(makeRunStarted({ event_id: "stale" }));
    expect(useTrialStore.getState().state).toBe(stateBeforeStaleEvent);
    expect(useTrialStore.getState().mode).toBe("replay");
  });

  it("tracks which trial id the buffered live events belong to", () => {
    vi.spyOn(client, "openTrialEventStream").mockReturnValue(() => {});
    useTrialStore.getState().startLive("trial-x");
    expect(useTrialStore.getState().liveTrialId).toBe("trial-x");
    useTrialStore.getState().reset();
    expect(useTrialStore.getState().liveTrialId).toBeNull();
  });

  it("reset clears everything back to idle", () => {
    useTrialStore.getState().loadForReplay([makeRunStarted()]);
    useTrialStore.getState().scrubTo(0);
    useTrialStore.getState().reset();
    const s = useTrialStore.getState();
    expect(s.mode).toBe("idle");
    expect(s.allEvents).toEqual([]);
    expect(s.state.status).toBe("idle");
  });
});
