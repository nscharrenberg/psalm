import type {
  CatalogResponse,
  PSALMEvent,
  TrialConfigInput,
  TrialDetail,
  TrialSummary,
} from "./types";

export class TrialConflictError extends Error {
  constructor() {
    super("A trial is already in progress.");
    this.name = "TrialConflictError";
  }
}

export class TrialConfigError extends Error {
  code: string;
  context: Record<string, unknown>;

  constructor(code: string, message: string, context: Record<string, unknown>) {
    super(message);
    this.name = "TrialConfigError";
    this.code = code;
    this.context = context;
  }
}

export async function getCatalog(): Promise<CatalogResponse> {
  const response = await fetch("/api/catalog");
  if (!response.ok) {
    throw new Error(`Failed to load catalog: ${response.status}`);
  }
  return response.json();
}

export async function startTrial(config: TrialConfigInput): Promise<{ trial_id: string }> {
  const response = await fetch("/api/trials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (response.status === 409) {
    throw new TrialConflictError();
  }
  if (response.status === 400) {
    const body = await response.json();
    const detail = body.detail as { code: string; message: string; context: Record<string, unknown> };
    throw new TrialConfigError(detail.code, detail.message, detail.context);
  }
  if (!response.ok) {
    throw new Error(`Failed to start trial: ${response.status}`);
  }
  return response.json();
}

export async function getTrial(id: string): Promise<TrialDetail> {
  const response = await fetch(`/api/trials/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to load trial ${id}: ${response.status}`);
  }
  return response.json();
}

export async function listTrials(): Promise<TrialSummary[]> {
  const response = await fetch("/api/trials");
  if (!response.ok) {
    throw new Error(`Failed to load trial history: ${response.status}`);
  }
  return response.json();
}

export function openTrialEventStream(
  id: string,
  onEvent: (event: PSALMEvent) => void,
  onClose?: () => void,
): () => void {
  const source = new EventSource(`/api/trials/${id}/events`);

  source.onmessage = (message) => {
    const event = JSON.parse(message.data) as PSALMEvent;
    onEvent(event);
    if (event.type === "final_verdict_reached" || event.type === "run_failed") {
      source.close();
      onClose?.();
    }
  };

  source.onerror = () => {
    // EventSource auto-retries transient network errors; only treat this as
    // terminal once the connection has actually closed.
    if (source.readyState === EventSource.CLOSED) {
      onClose?.();
    }
  };

  return () => source.close();
}
