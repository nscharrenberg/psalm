import { useEffect, useMemo, useRef } from "react";
import { Text, Timeline } from "@mantine/core";
import type { DimensionState, TranscriptEntry } from "../state/eventReducer";
import { mergeTranscript } from "../state/eventReducer";

interface TranscriptViewProps {
  dimension: DimensionState | null;
  sharedTranscript: TranscriptEntry[];
}

const ROLE_COLORS: Record<string, string> = {
  prosecution: "orange",
  defense: "blue",
};

function entryColor(entry: TranscriptEntry): string {
  if (["rejection", "validation", "consensus", "stability_check"].includes(entry.kind)) {
    return "grape";
  }
  if (entry.role && ROLE_COLORS[entry.role]) return ROLE_COLORS[entry.role];
  return "gray";
}

export default function TranscriptView({ dimension, sharedTranscript }: TranscriptViewProps) {
  const entries = useMemo(
    () => mergeTranscript(sharedTranscript, dimension),
    [sharedTranscript, dimension],
  );
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries.length]);

  if (entries.length === 0) {
    return <Text c="dimmed" className="transcript-empty">Waiting for the trial to begin...</Text>;
  }

  return (
    <div className="transcript-view" aria-live="polite" style={{ maxHeight: 480, overflowY: "auto" }}>
      <Timeline active={entries.length} bulletSize={14} lineWidth={2}>
        {entries.map((entry) => (
          <Timeline.Item key={entry.id} data-testid="transcript-entry" color={entryColor(entry)}>
            <Text size="sm">{entry.text}</Text>
          </Timeline.Item>
        ))}
      </Timeline>
      <div ref={bottomRef} />
    </div>
  );
}
