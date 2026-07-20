import { Stack, Stepper, Text } from "@mantine/core";
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

export default function TimelineView({ dimension, sharedTranscript }: TimelineViewProps) {
  if (dimension === null) {
    return <Text c="dimmed" className="timeline-empty">Waiting for the trial to begin...</Text>;
  }

  const steps = buildSteps(dimension);
  const currentIndex = steps.findIndex((s) => s.status === "current");
  const activeIndex = currentIndex === -1 ? steps.length : currentIndex;
  const entries = mergeTranscript(sharedTranscript, dimension);

  return (
    <Stack gap="lg" className="timeline-view">
      <Stepper active={activeIndex} orientation="vertical" size="sm" iconSize={22}>
        {steps.map((step, index) => (
          <Stepper.Step
            key={step.label} label={step.label}
            data-testid={`timeline-step-${index}`} data-status={step.status}
          />
        ))}
      </Stepper>
      <Stack gap="xs" className="timeline-transcript">
        {entries.map((entry) => (
          <Text key={entry.id} size="sm">{entry.text}</Text>
        ))}
      </Stack>
    </Stack>
  );
}
