import type { DimensionState } from "../state/eventReducer";

interface StageViewProps {
  dimension: DimensionState | null;
}

function phaseLabel(dimension: DimensionState): string {
  if (dimension.phase === "verdict") return `Verdict: ${dimension.verdict}`;
  if (dimension.phase === "deliberation") return `Deliberation — round ${dimension.currentRound}`;
  return `Argumentation — round ${dimension.currentRound}`;
}

export default function StageView({ dimension }: StageViewProps) {
  if (dimension === null) {
    return <p className="stage-empty">Waiting for the trial to begin...</p>;
  }

  const voteCounts = Object.values(dimension.jurorVotes).reduce<Record<string, number>>((acc, v) => {
    acc[v.vote] = (acc[v.vote] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="stage-view">
      <div className="stage-phase-indicator">{phaseLabel(dimension)}</div>

      <div className="stage-bench" data-testid="stage-bench">
        <span className="stage-role-label">Judge</span>
        {dimension.rejectedArgumentCount > 0 && (
          <p className="stage-speech">{dimension.rejectedArgumentCount} objection(s) sustained so far.</p>
        )}
      </div>

      <div className="stage-parties">
        <div
          data-testid="stage-podium-prosecution"
          className={`stage-podium ${dimension.speakingRole === "prosecution" ? "stage-speaking" : ""}`}
        >
          <span className="stage-role-label">Prosecutor</span>
          {dimension.speakingRole === "prosecution" && dimension.latestSpeech && (
            <p className="stage-speech">&quot;{dimension.latestSpeech}&quot;</p>
          )}
        </div>
        <div
          data-testid="stage-podium-defense"
          className={`stage-podium ${dimension.speakingRole === "defense" ? "stage-speaking" : ""}`}
        >
          <span className="stage-role-label">Defense</span>
          {dimension.speakingRole === "defense" && dimension.latestSpeech && (
            <p className="stage-speech">&quot;{dimension.latestSpeech}&quot;</p>
          )}
        </div>
      </div>

      <div className="stage-jury" data-testid="stage-jury">
        <span className="stage-role-label">Jury ({Object.keys(dimension.jurorVotes).length} voted)</span>
        <div className="stage-jury-tally">
          {Object.entries(voteCounts).map(([vote, count]) => (
            <span key={vote} className="stage-jury-vote">{count} × {vote}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
