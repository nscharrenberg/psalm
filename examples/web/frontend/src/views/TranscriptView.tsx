import { useMemo } from "react";
import type { DimensionState, TranscriptEntry } from "../state/eventReducer";
import { mergeTranscript } from "../state/eventReducer";

interface TranscriptViewProps {
  dimension: DimensionState | null;
  sharedTranscript: TranscriptEntry[];
}

const ROLE_COLORS: Record<string, string> = {
  prosecution: "#b45309",
  defense: "#1d4ed8",
};

function entryColor(entry: TranscriptEntry): string {
  if (["rejection", "validation", "consensus", "stability_check"].includes(entry.kind)) {
    return "#6b21a8";
  }
  if (entry.role && ROLE_COLORS[entry.role]) return ROLE_COLORS[entry.role];
  return "#4b5563";
}

export default function TranscriptView({ dimension, sharedTranscript }: TranscriptViewProps) {
  const entries = useMemo(
    () => mergeTranscript(sharedTranscript, dimension),
    [sharedTranscript, dimension],
  );

  if (entries.length === 0) {
    return <p className="transcript-empty">Waiting for the trial to begin...</p>;
  }

  return (
    <div className="transcript-view" aria-live="polite">
      {entries.map((entry) => (
        <div
          key={entry.id}
          data-testid="transcript-entry"
          className="transcript-entry"
          style={{ borderLeftColor: entryColor(entry) }}
        >
          {entry.text}
        </div>
      ))}
    </div>
  );
}
