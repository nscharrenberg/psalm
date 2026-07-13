// --- Catalog (mirrors examples/web/backend/schemas.py's CatalogResponse family) ---

export interface SubDimension {
  name: string;
  description: string;
  importance: string;
}

export interface DimensionCatalogEntry {
  name: string;
  dimension_type: "infringement" | "exception";
  importance: string;
  description: string;
  sub_dimensions: SubDimension[];
}

export interface Preset {
  id: string;
  label: string;
  source_text: string;
  target_text: string;
}

export interface EvaluationStrategyOption {
  value: "fully_separate" | "shared_arg_per_dim_deliberation" | "shared_all";
  label: string;
  description: string;
}

export interface ProviderPreset {
  id: string;
  label: string;
  base_url: string;
}

export interface CatalogResponse {
  dimensions: DimensionCatalogEntry[];
  presets: Preset[];
  evaluation_strategies: EvaluationStrategyOption[];
  provider_presets: ProviderPreset[];
  env_status: Record<string, boolean>;
}

// --- Trial request (mirrors TrialConfigRequest / AgentConfigRequest / JurorConfigRequest) ---

export interface AgentConfigInput {
  base_url?: string;
  api_key?: string;
  model?: string;
  temperature?: number;
}

export interface JurorConfigInput extends AgentConfigInput {
  seed?: number;
}

export interface TrialConfigInput {
  source_text: string;
  target_text: string;
  dimensions: string[];
  evaluation_strategy: string;
  argumentation_rounds: number;
  deliberation_rounds: number;
  time_limit_seconds: number;
  prosecutor: AgentConfigInput;
  defense: AgentConfigInput;
  judge: AgentConfigInput;
  jury: JurorConfigInput[];
}

// --- Trial response (mirrors TrialSummary / TrialDetail) ---

export interface TrialSummary {
  id: string;
  created_at: string;
  status: "running" | "done" | "error";
  source_text_preview: string;
  target_text_preview: string;
  verdict: string | null;
  error_message: string | null;
}

export interface TrialDetail extends TrialSummary {
  config_summary: Record<string, unknown>;
  result: PSALMResult | null;
}

// --- Result shapes (mirrors psalm/models/evidence.py and psalm/models/result.py) ---

export interface Proof {
  source_excerpt: string;
  target_excerpt: string;
  relevance: string;
}

export interface Argument {
  claim: string;
  dimension: string;
  proofs: Proof[];
  agent_role: string;
  round: number;
}

export interface RejectedArgument {
  argument: Argument;
  rejection_reason: string;
}

export interface DimensionScore {
  sub_dimension: string;
  score: "none" | "generic" | "possible" | "clear";
  reasoning: string;
}

export interface JurorVote {
  juror_id: string;
  vote: "Guilty" | "Not Guilty" | "Undecided";
  rationale: string;
  dimension_scores: DimensionScore[];
  dimension: string | null;
}

export interface RoundArguments {
  round: number;
  prosecution_arguments: Argument[];
  prosecution_rejected_arguments: RejectedArgument[];
  prosecution_closing_statement: string | null;
  defense_counters: Argument[];
  defense_counter_rejected_arguments: RejectedArgument[];
  defense_counter_closing_statement: string | null;
  defense_arguments: Argument[];
  defense_rejected_arguments: RejectedArgument[];
  defense_closing_statement: string | null;
  prosecution_counters: Argument[];
  prosecution_counter_rejected_arguments: RejectedArgument[];
  prosecution_counter_closing_statement: string | null;
}

export interface RoundDeliberation {
  round: number;
  discussion_messages: { juror_id: string; message: string }[];
  votes: JurorVote[];
  aggregated_result: string | null;
}

export interface ArgumentationLog {
  rounds: RoundArguments[];
  prosecution_closing_argument: string | null;
  defense_closing_argument: string | null;
}

export interface DebateLog {
  rounds: RoundDeliberation[];
  final_voting_strategy_applied: string;
}

export interface DimensionVerdict {
  dimension: string;
  dimension_type: "infringement" | "exception";
  importance: string;
  verdict: "Guilty" | "Not Guilty" | "Undecided";
  weighted_score: number;
  argumentation_log: ArgumentationLog;
  debate_log: DebateLog;
}

export interface ResultMetadata {
  duration_seconds: number;
  argumentation_rounds_used: number;
  deliberation_rounds_used: number;
  voting_strategy_applied: string;
  agent_failures: unknown[];
}

export interface PSALMResult {
  verdict: "Guilty" | "Not Guilty" | "Undecided";
  rationale: string;
  dimension_verdicts: DimensionVerdict[];
  metadata: ResultMetadata;
}

// --- Event envelope + discriminated union (mirrors psalm/events/types.py) ---

interface EventEnvelope {
  event_id: string;
  sequence: number;
  timestamp: string;
  run_id: string;
  dimension: string | null;
}

export interface RunStarted extends EventEnvelope {
  category: "lifecycle";
  type: "run_started";
  dimensions: string[];
  evaluation_strategy: string;
  source_length: number;
  target_length: number;
}

export interface RunFailed extends EventEnvelope {
  category: "lifecycle";
  type: "run_failed";
  code: string;
  message: string;
  context: Record<string, unknown>;
}

export interface DimensionStarted extends EventEnvelope {
  category: "lifecycle";
  type: "dimension_started";
  dimension_type: string;
  importance: string;
}

export interface ArgumentationRoundStarted extends EventEnvelope {
  category: "argumentation";
  type: "argumentation_round_started";
  round: number;
}

export interface ArgumentSubmitted extends EventEnvelope {
  category: "argumentation";
  type: "argument_submitted";
  round: number;
  role: "prosecution" | "defense";
  kind: "argument" | "counter";
  argument: Argument;
}

export interface ArgumentValidated extends EventEnvelope {
  category: "argumentation";
  type: "argument_validated";
  round: number;
  role: string;
  argument: Argument;
}

export interface ArgumentRejected extends EventEnvelope {
  category: "argumentation";
  type: "argument_rejected";
  round: number;
  role: string;
  argument: Argument;
  reason: string;
}

export interface ClosingStatementDelivered extends EventEnvelope {
  category: "argumentation";
  type: "closing_statement_delivered";
  round: number;
  role: string;
  statement: string;
}

export interface ArgumentationStabilityChecked extends EventEnvelope {
  category: "argumentation";
  type: "argumentation_stability_checked";
  round: number;
  stability_detected: boolean;
}

export interface ClosingArgumentDelivered extends EventEnvelope {
  category: "argumentation";
  type: "closing_argument_delivered";
  role: string;
  statement: string;
}

export interface ArgumentBatchCompletenessRetry extends EventEnvelope {
  category: "argumentation";
  type: "argument_batch_completeness_retry";
  round: number;
  role: string;
  attempt: number;
  max_attempts: number;
}

export interface DeliberationRoundStarted extends EventEnvelope {
  category: "deliberation";
  type: "deliberation_round_started";
  round: number;
}

export interface JurorVoteCast extends EventEnvelope {
  category: "deliberation";
  type: "juror_vote_cast";
  round: number;
  juror_id: string;
  vote: string;
  rationale: string;
  dimension_scores: DimensionScore[];
}

export interface JuryConsensusChecked extends EventEnvelope {
  category: "deliberation";
  type: "jury_consensus_checked";
  round: number;
  is_unanimous: boolean;
  top_verdict: string | null;
}

export interface JuryDiscussionMessage extends EventEnvelope {
  category: "deliberation";
  type: "jury_discussion_message";
  round: number;
  juror_id: string;
  message: string;
}

export interface VotingStrategyApplied extends EventEnvelope {
  category: "deliberation";
  type: "voting_strategy_applied";
  strategy_name: string;
  is_tie: boolean;
  verdict: string | null;
}

export interface DimensionVerdictReached extends EventEnvelope {
  category: "verdict";
  type: "dimension_verdict_reached";
  dimension_type: string;
  importance: string;
  verdict: string;
  weighted_score: number;
}

export interface FinalVerdictReached extends EventEnvelope {
  category: "verdict";
  type: "final_verdict_reached";
  result: PSALMResult;
}

export interface AgentCallRetrying extends EventEnvelope {
  category: "agent";
  type: "agent_call_retrying";
  role: string;
  attempt: number;
  max_attempts: number;
  backoff_seconds: number;
  error: string;
}

export interface AgentCallFailed extends EventEnvelope {
  category: "agent";
  type: "agent_call_failed";
  role: string;
  attempts: number;
  code: string;
  error: string;
}

export type PSALMEvent =
  | RunStarted
  | RunFailed
  | DimensionStarted
  | ArgumentationRoundStarted
  | ArgumentSubmitted
  | ArgumentValidated
  | ArgumentRejected
  | ClosingStatementDelivered
  | ArgumentationStabilityChecked
  | ClosingArgumentDelivered
  | ArgumentBatchCompletenessRetry
  | DeliberationRoundStarted
  | JurorVoteCast
  | JuryConsensusChecked
  | JuryDiscussionMessage
  | VotingStrategyApplied
  | DimensionVerdictReached
  | FinalVerdictReached
  | AgentCallRetrying
  | AgentCallFailed;
