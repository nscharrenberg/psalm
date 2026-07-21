import { afterEach, describe, expect, it, vi } from "vitest";
import {
  TrialConfigError,
  TrialConflictError,
  fetchTrialEvents,
  getCatalog,
  getTrial,
  listTrials,
  openTrialEventStream,
  startTrial,
} from "./client";
import type { TrialConfigInput } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

const sampleConfig: TrialConfigInput = {
  source_text: "s", target_text: "t", dimensions: ["Character"], evaluation_strategy: "fully_separate",
  argumentation_rounds: 3, deliberation_rounds: 2, time_limit_seconds: 120,
  max_concurrent_llm_calls: 8, max_retries: 3,
  prosecutor: {}, defense: {}, judge: {}, jury: [],
};

describe("getCatalog", () => {
  it("fetches and parses the catalog", async () => {
    const fakeCatalog = { dimensions: [], presets: [], evaluation_strategies: [], provider_presets: [], env_status: {} };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => fakeCatalog }));
    const result = await getCatalog();
    expect(result).toEqual(fakeCatalog);
    expect(fetch).toHaveBeenCalledWith("/api/catalog");
  });
});

describe("startTrial", () => {
  it("returns the trial_id on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 202, json: async () => ({ trial_id: "abc" }) }));
    const result = await startTrial(sampleConfig);
    expect(result).toEqual({ trial_id: "abc" });
  });

  it("throws TrialConflictError on 409", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409 }));
    await expect(startTrial(sampleConfig)).rejects.toBeInstanceOf(TrialConflictError);
  });

  it("throws TrialConfigError with code/message/context on 400", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 400,
      json: async () => ({ detail: { code: "PSALM-WEB-001", message: "No API key", context: {} } }),
    }));
    const error = await startTrial(sampleConfig).catch((e) => e);
    expect(error).toBeInstanceOf(TrialConfigError);
    expect(error.code).toBe("PSALM-WEB-001");
    expect(error.message).toBe("No API key");
  });
});

describe("getTrial", () => {
  it("fetches trial detail by id", async () => {
    const fakeDetail = { id: "abc", status: "done" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => fakeDetail }));
    const result = await getTrial("abc");
    expect(result).toEqual(fakeDetail);
    expect(fetch).toHaveBeenCalledWith("/api/trials/abc");
  });
});

describe("listTrials", () => {
  it("fetches the trial history list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    const result = await listTrials();
    expect(result).toEqual([]);
  });
});

describe("openTrialEventStream", () => {
  class FakeEventSource {
    static CLOSED = 2;
    static instances: FakeEventSource[] = [];
    readyState = 1;
    onmessage: ((event: { data: string }) => void) | null = null;
    onerror: (() => void) | null = null;
    url: string;
    constructor(url: string) {
      this.url = url;
      FakeEventSource.instances.push(this);
    }
    close() {
      this.readyState = FakeEventSource.CLOSED;
    }
  }

  it("parses incoming messages and forwards them to the callback", () => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);

    const received: unknown[] = [];
    openTrialEventStream("abc", (event) => received.push(event));

    const source = FakeEventSource.instances[0];
    source.onmessage?.({ data: JSON.stringify({ type: "run_started" }) });

    expect(received).toEqual([{ type: "run_started" }]);
    expect(source.url).toBe("/api/trials/abc/events");
  });

  it("closes the connection and calls onClose after final_verdict_reached", () => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);

    let closed = false;
    openTrialEventStream("abc", () => {}, () => { closed = true; });

    const source = FakeEventSource.instances[0];
    source.onmessage?.({ data: JSON.stringify({ type: "final_verdict_reached" }) });

    expect(source.readyState).toBe(FakeEventSource.CLOSED);
    expect(closed).toBe(true);
  });

  it("returns a function that closes the connection early", () => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);

    const close = openTrialEventStream("abc", () => {});
    close();

    expect(FakeEventSource.instances[0].readyState).toBe(FakeEventSource.CLOSED);
  });

  describe("fetchTrialEvents", () => {
    it("accumulates every streamed event and resolves once the stream closes", async () => {
      FakeEventSource.instances = [];
      vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);

      const resultPromise = fetchTrialEvents("abc");

      const source = FakeEventSource.instances[0];
      expect(source.url).toBe("/api/trials/abc/events");
      source.onmessage?.({ data: JSON.stringify({ type: "run_started" }) });
      source.onmessage?.({ data: JSON.stringify({ type: "final_verdict_reached" }) });

      const result = await resultPromise;
      expect(result).toEqual([{ type: "run_started" }, { type: "final_verdict_reached" }]);
    });
  });
});
