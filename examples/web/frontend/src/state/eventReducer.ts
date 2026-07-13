import type { DimensionScore, PSALMEvent, PSALMResult } from "../api/types";

export interface TranscriptEntry {
  id: string;
  timestamp: string;
  dimension: string | null;
  kind: string;
  role?: string;
  text: string;
  raw: PSALMEvent;
}

export interface DimensionState {
  name: string;
  dimensionType: string | null;
  importance: string | null;
  phase: "argumentation" | "deliberation" | "verdict";
  currentRound: number;
  status: "running" | "done";
  verdict: string | null;
  weightedScore: number | null;
  speakingRole: string | null;
  latestSpeech: string | null;
  jurorVotes: Record<string, { vote: string; rationale: string; dimensionScores: DimensionScore[] }>;
  rejectedArgumentCount: number;
  transcript: TranscriptEntry[];
}

export interface TrialState {
  runId: string | null;
  status: "idle" | "running" | "done" | "error";
  evaluationStrategy: string | null;
  dimensionOrder: string[];
  dimensions: Record<string, DimensionState>;
  sharedTranscript: TranscriptEntry[];
  finalResult: PSALMResult | null;
  errorMessage: string | null;
}

export function createInitialState(): TrialState {
  return {
    runId: null,
    status: "idle",
    evaluationStrategy: null,
    dimensionOrder: [],
    dimensions: {},
    sharedTranscript: [],
    finalResult: null,
    errorMessage: null,
  };
}

function ensureDimension(state: TrialState, name: string): TrialState {
  if (state.dimensions[name]) return state;
  const dimensionState: DimensionState = {
    name, dimensionType: null, importance: null, phase: "argumentation", currentRound: 0,
    status: "running", verdict: null, weightedScore: null, speakingRole: null, latestSpeech: null,
    jurorVotes: {}, rejectedArgumentCount: 0, transcript: [],
  };
  return {
    ...state,
    dimensionOrder: [...state.dimensionOrder, name],
    dimensions: { ...state.dimensions, [name]: dimensionState },
  };
}

function appendEntry(dim: DimensionState, entry: TranscriptEntry): DimensionState {
  return { ...dim, transcript: [...dim.transcript, entry] };
}

function updateDimension(
  state: TrialState, name: string, updater: (dim: DimensionState) => DimensionState,
): TrialState {
  const current = state.dimensions[name];
  if (!current) return state;
  return { ...state, dimensions: { ...state.dimensions, [name]: updater(current) } };
}

function appendShared(state: TrialState, entry: TranscriptEntry): TrialState {
  return { ...state, sharedTranscript: [...state.sharedTranscript, entry] };
}

export function applyEvent(state: TrialState, event: PSALMEvent): TrialState {
  switch (event.type) {
    case "run_started":
      return {
        ...state, runId: event.run_id, status: "running", evaluationStrategy: event.evaluation_strategy,
      };

    case "run_failed":
      return { ...state, status: "error", errorMessage: event.message };

    case "dimension_started": {
      if (event.dimension === null) return state;
      const withDim = ensureDimension(state, event.dimension);
      return updateDimension(withDim, event.dimension, (dim) => ({
        ...dim, dimensionType: event.dimension_type, importance: event.importance,
      }));
    }

    case "argumentation_round_started": {
      if (event.dimension === null) return state;
      return updateDimension(state, event.dimension, (dim) => ({
        ...dim, phase: "argumentation", currentRound: event.round,
      }));
    }

    case "argument_submitted": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "argument", role: event.role,
        text: `${event.role === "prosecution" ? "Prosecutor" : "Defense"} `
          + `${event.kind === "counter" ? "counters" : "argues"}: "${event.argument.claim}"`,
        raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(
        { ...dim, speakingRole: event.role, latestSpeech: event.argument.claim }, entry,
      ));
    }

    case "argument_validated": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "validation", role: event.role, text: `Judge accepts the ${event.role} argument.`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "argument_rejected": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "rejection", role: event.role, text: `Judge sustains an objection: "${event.reason}"`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(
        { ...dim, rejectedArgumentCount: dim.rejectedArgumentCount + 1 }, entry,
      ));
    }

    case "closing_statement_delivered": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "closing_statement", role: event.role, text: `${event.role}: "${event.statement}"`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "argumentation_stability_checked": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "stability_check",
        text: event.stability_detected ? "The argumentation has stabilized." : "Argumentation continues.",
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "closing_argument_delivered": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "closing_argument", role: event.role,
        text: `${event.role} closing argument: "${event.statement}"`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "argument_batch_completeness_retry": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "completeness_retry", role: event.role,
        text: `The Judge asks the ${event.role} to clarify (attempt ${event.attempt}/${event.max_attempts}).`,
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "deliberation_round_started": {
      if (event.dimension === null) return state;
      return updateDimension(state, event.dimension, (dim) => ({
        ...dim, phase: "deliberation", currentRound: event.round,
      }));
    }

    case "juror_vote_cast": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "vote", role: event.juror_id, text: `${event.juror_id} votes ${event.vote}.`, raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry({
        ...dim,
        jurorVotes: {
          ...dim.jurorVotes,
          [event.juror_id]: {
            vote: event.vote, rationale: event.rationale, dimensionScores: event.dimension_scores,
          },
        },
      }, entry));
    }

    case "jury_consensus_checked": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "consensus",
        text: event.is_unanimous
          ? `The jury unanimously finds ${event.top_verdict}.`
          : "The jury has not reached consensus.",
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "jury_discussion_message": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "discussion", role: event.juror_id, text: `${event.juror_id}: "${event.message}"`, raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(
        { ...dim, speakingRole: event.juror_id, latestSpeech: event.message }, entry,
      ));
    }

    case "voting_strategy_applied": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "voting_strategy",
        text: event.is_tie
          ? `${event.strategy_name} could not break the tie.`
          : `${event.strategy_name} resolves the vote: ${event.verdict}.`,
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "dimension_verdict_reached": {
      if (event.dimension === null) return state;
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "dimension_verdict",
        text: `Verdict for ${event.dimension}: ${event.verdict} (score ${event.weighted_score.toFixed(2)}).`,
        raw: event,
      };
      return updateDimension(state, event.dimension, (dim) => appendEntry(
        { ...dim, phase: "verdict", status: "done", verdict: event.verdict, weightedScore: event.weighted_score },
        entry,
      ));
    }

    case "final_verdict_reached":
      return { ...state, status: "done", finalResult: event.result };

    case "agent_call_retrying": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "agent_retry", role: event.role,
        text: `${event.role} had a transient error, retrying (attempt ${event.attempt}/${event.max_attempts})...`,
        raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    case "agent_call_failed": {
      const entry: TranscriptEntry = {
        id: event.event_id, timestamp: event.timestamp, dimension: event.dimension,
        kind: "agent_failure", role: event.role,
        text: `${event.role} failed after ${event.attempts} attempts: ${event.error}`, raw: event,
      };
      if (event.dimension === null) return appendShared(state, entry);
      return updateDimension(state, event.dimension, (dim) => appendEntry(dim, entry));
    }

    default: {
      const _exhaustive: never = event;
      void _exhaustive;
      return state;
    }
  }
}
