import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getTrial } from "../api/client";
import type { TrialDetail } from "../api/types";
import { useTrialStore } from "../state/store";
import StageView from "../views/StageView";

export default function ResultsPage() {
  const { trialId } = useParams<{ trialId: string }>();
  const [detail, setDetail] = useState<TrialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showReplay, setShowReplay] = useState(false);
  const [replayDimension, setReplayDimension] = useState<string | null>(null);

  const liveEvents = useTrialStore((s) => s.allEvents);
  const liveTrialId = useTrialStore((s) => s.liveTrialId);
  const loadForReplay = useTrialStore((s) => s.loadForReplay);
  const replayState = useTrialStore((s) => s.state);
  const replayMode = useTrialStore((s) => s.mode);
  const isPlaying = useTrialStore((s) => s.isPlaying);
  const replayIndex = useTrialStore((s) => s.replayIndex);
  const play = useTrialStore((s) => s.play);
  const pause = useTrialStore((s) => s.pause);
  const scrubTo = useTrialStore((s) => s.scrubTo);

  useEffect(() => {
    if (!trialId) return;
    getTrial(trialId).then(setDetail).catch((e) => setError(String(e)));
  }, [trialId]);

  // Mirrors LiveTrialPage's dimension auto-select: the dimension-selector buttons
  // only render when there's more than one dimension, so for the common
  // single-dimension case nothing would ever call setReplayDimension and
  // StageView would be stuck showing "Waiting for the trial to begin..."
  // forever despite real replay data being available. This effect must depend
  // on replayState.dimensionOrder (not run once on mount) because it's only
  // populated once loadForReplay(liveEvents) runs from startReplay().
  useEffect(() => {
    if (!replayDimension && replayState.dimensionOrder.length > 0) {
      setReplayDimension(replayState.dimensionOrder[0]);
    }
  }, [replayState.dimensionOrder, replayDimension]);

  function startReplay() {
    loadForReplay(liveEvents);
    setShowReplay(true);
  }

  if (error) return <p role="alert">Failed to load trial: {error}</p>;
  if (!detail) return <p>Loading...</p>;

  const result = detail.result;

  return (
    <div className="results-page">
      <h1>Trial result</h1>
      {detail.status === "error" && <p role="alert">Trial failed: {detail.error_message}</p>}

      {result && (
        <>
          <section className="verdict-banner">
            <h2>Verdict: {result.verdict}</h2>
            <p>{result.rationale}</p>
          </section>

          <section>
            <h2>Per-dimension breakdown</h2>
            <table>
              <thead>
                <tr>
                  <th>Dimension</th><th>Type</th><th>Importance</th><th>Verdict</th><th>Score</th>
                </tr>
              </thead>
              <tbody>
                {result.dimension_verdicts.map((dv) => (
                  <tr key={dv.dimension}>
                    <td>{dv.dimension}</td>
                    <td>{dv.dimension_type}</td>
                    <td>{dv.importance}</td>
                    <td>{dv.verdict}</td>
                    <td>{dv.weighted_score.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {result.dimension_verdicts.map((dv) => (
            <details key={dv.dimension}>
              <summary>{dv.dimension} — full log</summary>
              <h3>Argumentation</h3>
              {dv.argumentation_log.rounds.map((round) => (
                <div key={round.round}>
                  <h4>Round {round.round}</h4>
                  {round.prosecution_arguments.map((arg, i) => <p key={`pa${i}`}>Prosecution: {arg.claim}</p>)}
                  {round.prosecution_rejected_arguments.map((rej, i) => (
                    <p key={`pr${i}`}>Rejected (prosecution): {rej.argument.claim} — {rej.rejection_reason}</p>
                  ))}
                  {round.defense_counters.map((arg, i) => <p key={`dc${i}`}>Defense counters: {arg.claim}</p>)}
                  {round.defense_counter_rejected_arguments.map((rej, i) => (
                    <p key={`dcr${i}`}>Rejected (defense counter): {rej.argument.claim} — {rej.rejection_reason}</p>
                  ))}
                  {round.defense_arguments.map((arg, i) => <p key={`da${i}`}>Defense: {arg.claim}</p>)}
                  {round.defense_rejected_arguments.map((rej, i) => (
                    <p key={`dr${i}`}>Rejected (defense): {rej.argument.claim} — {rej.rejection_reason}</p>
                  ))}
                  {round.prosecution_counters.map((arg, i) => (
                    <p key={`pc${i}`}>Prosecution counters: {arg.claim}</p>
                  ))}
                  {round.prosecution_counter_rejected_arguments.map((rej, i) => (
                    <p key={`pcr${i}`}>Rejected (prosecution counter): {rej.argument.claim} — {rej.rejection_reason}</p>
                  ))}
                </div>
              ))}
              {dv.argumentation_log.prosecution_closing_argument && (
                <p>Prosecution closing: {dv.argumentation_log.prosecution_closing_argument}</p>
              )}
              {dv.argumentation_log.defense_closing_argument && (
                <p>Defense closing: {dv.argumentation_log.defense_closing_argument}</p>
              )}

              <h3>Deliberation</h3>
              {dv.debate_log.rounds.map((round) => (
                <div key={round.round}>
                  <h4>Round {round.round}</h4>
                  {round.votes.map((vote) => (
                    <p key={vote.juror_id}>{vote.juror_id}: {vote.vote} — {vote.rationale}</p>
                  ))}
                  {round.discussion_messages.map((msg, i) => (
                    <p key={i}>{msg.juror_id}: {msg.message}</p>
                  ))}
                </div>
              ))}
            </details>
          ))}
        </>
      )}

      {liveTrialId === trialId && liveEvents.length > 0 && !showReplay && (
        <button type="button" onClick={startReplay}>Replay this trial</button>
      )}

      {showReplay && replayMode === "replay" && (
        <section className="replay-section">
          <h2>Replay</h2>
          {replayState.dimensionOrder.length > 1 && (
            <div className="dimension-selector">
              {replayState.dimensionOrder.map((name) => (
                <button
                  key={name} type="button"
                  className={name === replayDimension ? "active" : ""}
                  onClick={() => setReplayDimension(name)}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
          <div className="replay-controls">
            <button type="button" onClick={isPlaying ? pause : play}>{isPlaying ? "Pause" : "Play"}</button>
            <input
              type="range" min={-1} max={liveEvents.length - 1} value={replayIndex}
              onChange={(e) => scrubTo(Number(e.target.value))}
            />
          </div>
          <StageView dimension={replayDimension ? replayState.dimensions[replayDimension] ?? null : null} />
        </section>
      )}
    </div>
  );
}
