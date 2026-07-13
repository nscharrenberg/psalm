import type { DimensionState, TranscriptEntry } from "../state/eventReducer";
import { mergeTranscript } from "../state/eventReducer";

interface TimelineViewProps {
  dimension: DimensionState | null;
  sharedTranscript: TranscriptEntry[];
}

interface StepInfo {
  label: string;
  status: "done" | "current" | "upcoming";
}

function buildSteps(dimension: DimensionState): StepInfo[] {
  const steps: StepInfo[] = [{ label: "Setup", status: "done" }];
  const maxKnownRound = Math.max(dimension.currentRound, 1);
  for (let round = 1; round <= maxKnownRound; round++) {
    let status: StepInfo["status"] = "done";
    if (dimension.phase === "argumentation" && round === dimension.currentRound) status = "current";
    if (round > dimension.currentRound) status = "upcoming";
    steps.push({ label: `Argumentation round ${round}`, status });
  }
  steps.push({
    label: "Deliberation",
    status: dimension.phase === "deliberation" ? "current" : dimension.phase === "verdict" ? "done" : "upcoming",
  });
  steps.push({ label: "Verdict", status: dimension.phase === "verdict" ? "done" : "upcoming" });
  return steps;
}

function statusIcon(status: StepInfo["status"]): string {
  if (status === "done") return "✅";
  if (status === "current") return "▶";
  return "○";
}

export default function TimelineView({ dimension, sharedTranscript }: TimelineViewProps) {
  if (dimension === null) {
    return <p className="timeline-empty">Waiting for the trial to begin...</p>;
  }

  const steps = buildSteps(dimension);
  const entries = mergeTranscript(sharedTranscript, dimension);

  return (
    <div className="timeline-view">
      <div className="timeline-steps">
        {steps.map((step) => (
          <div key={step.label} className={`timeline-step timeline-step-${step.status}`}>
            {statusIcon(step.status)} {step.label}
          </div>
        ))}
      </div>
      <div className="timeline-transcript">
        {entries.map((entry) => (
          <div key={entry.id} className="timeline-entry">{entry.text}</div>
        ))}
      </div>
    </div>
  );
}
