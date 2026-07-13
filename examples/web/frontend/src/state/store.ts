import { create } from "zustand";
import { openTrialEventStream } from "../api/client";
import type { PSALMEvent } from "../api/types";
import { applyEvent, createInitialState } from "./eventReducer";
import type { TrialState } from "./eventReducer";

export type PlaybackMode = "idle" | "live" | "replay";

interface TrialStoreState {
  mode: PlaybackMode;
  state: TrialState;
  allEvents: PSALMEvent[];
  isPlaying: boolean;
  replaySpeed: number;
  replayIndex: number;

  startLive: (trialId: string) => void;
  stopLive: () => void;
  reset: () => void;
  loadForReplay: (events: PSALMEvent[]) => void;
  play: () => void;
  pause: () => void;
  scrubTo: (index: number) => void;
  setReplaySpeed: (speed: number) => void;
}

let closeLiveStream: (() => void) | null = null;
let replayTimer: ReturnType<typeof setInterval> | null = null;

function stopReplayTimer(): void {
  if (replayTimer !== null) {
    clearInterval(replayTimer);
    replayTimer = null;
  }
}

function reduceUpTo(events: PSALMEvent[], index: number): TrialState {
  let state = createInitialState();
  for (let i = 0; i <= index && i < events.length; i++) {
    state = applyEvent(state, events[i]);
  }
  return state;
}

export const useTrialStore = create<TrialStoreState>((set, get) => ({
  mode: "idle",
  state: createInitialState(),
  allEvents: [],
  isPlaying: false,
  replaySpeed: 1,
  replayIndex: -1,

  startLive: (trialId: string) => {
    closeLiveStream?.();
    stopReplayTimer();
    set({ mode: "live", state: createInitialState(), allEvents: [], isPlaying: false, replayIndex: -1 });
    // Track staleness per-stream so that closing the stream (via closeLiveStream)
    // immediately silences its onEvent callback, even if an in-flight event still
    // fires after close() is requested (e.g. the underlying transport isn't
    // perfectly synchronous). Without this, a leftover live stream could mutate
    // `state`/`allEvents` after loadForReplay/startLive/reset has moved on.
    let isStale = false;
    const unsubscribe = openTrialEventStream(
      trialId,
      (event) => {
        if (isStale) return;
        set((s) => ({ state: applyEvent(s.state, event), allEvents: [...s.allEvents, event] }));
      },
      () => {
        closeLiveStream = null;
      },
    );
    closeLiveStream = () => {
      isStale = true;
      unsubscribe();
    };
  },

  stopLive: () => {
    closeLiveStream?.();
    closeLiveStream = null;
    stopReplayTimer();
  },

  reset: () => {
    closeLiveStream?.();
    closeLiveStream = null;
    stopReplayTimer();
    set({ mode: "idle", state: createInitialState(), allEvents: [], isPlaying: false, replayIndex: -1 });
  },

  loadForReplay: (events: PSALMEvent[]) => {
    closeLiveStream?.();
    closeLiveStream = null;
    stopReplayTimer();
    set({ mode: "replay", allEvents: events, replayIndex: -1, state: createInitialState(), isPlaying: false });
  },

  play: () => {
    stopReplayTimer();
    set({ isPlaying: true });
    const tick = () => {
      const { allEvents, replayIndex } = get();
      const nextIndex = replayIndex + 1;
      if (nextIndex >= allEvents.length) {
        stopReplayTimer();
        set({ isPlaying: false });
        return;
      }
      set({ replayIndex: nextIndex, state: reduceUpTo(allEvents, nextIndex) });
    };
    const { replaySpeed } = get();
    replayTimer = setInterval(tick, Math.max(20, 400 / replaySpeed));
  },

  pause: () => {
    stopReplayTimer();
    set({ isPlaying: false });
  },

  scrubTo: (index: number) => {
    stopReplayTimer();
    set((s) => {
      const clamped = Math.max(-1, Math.min(index, s.allEvents.length - 1));
      return { replayIndex: clamped, state: reduceUpTo(s.allEvents, clamped), isPlaying: false };
    });
  },

  setReplaySpeed: (speed: number) => {
    set({ replaySpeed: speed });
    if (get().isPlaying) {
      get().play();
    }
  },
}));
