import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTrialStore } from "../state/store";
import StageView from "../views/StageView";
import TimelineView from "../views/TimelineView";
import TranscriptView from "../views/TranscriptView";

type ViewName = "stage" | "transcript" | "timeline";

const VIEW_LABELS: Record<ViewName, string> = {
  stage: "Stage", transcript: "Transcript", timeline: "Timeline",
};

export default function LiveTrialPage() {
  const { trialId } = useParams<{ trialId: string }>();
  const navigate = useNavigate();
  const trialState = useTrialStore((s) => s.state);
  const startLive = useTrialStore((s) => s.startLive);
  const [activeView, setActiveView] = useState<ViewName>("stage");
  const [selectedDimension, setSelectedDimension] = useState<string | null>(null);

  useEffect(() => {
    if (trialId) startLive(trialId);
  }, [trialId, startLive]);

  useEffect(() => {
    if ((trialState.status === "done" || trialState.status === "error") && trialId) {
      navigate(`/trial/${trialId}/result`);
    }
  }, [trialState.status, trialId, navigate]);

  useEffect(() => {
    if (!selectedDimension && trialState.dimensionOrder.length > 0) {
      setSelectedDimension(trialState.dimensionOrder[0]);
    }
  }, [trialState.dimensionOrder, selectedDimension]);

  const dimension = selectedDimension ? trialState.dimensions[selectedDimension] ?? null : null;

  return (
    <div className="live-trial-page">
      <h1>Trial in progress</h1>

      {trialState.dimensionOrder.length > 1 && (
        <div className="dimension-selector">
          {trialState.dimensionOrder.map((name) => (
            <button
              key={name}
              type="button"
              className={name === selectedDimension ? "active" : ""}
              onClick={() => setSelectedDimension(name)}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      <div className="view-tabs">
        {(Object.keys(VIEW_LABELS) as ViewName[]).map((view) => (
          <button
            key={view}
            type="button"
            className={view === activeView ? "active" : ""}
            onClick={() => setActiveView(view)}
          >
            {VIEW_LABELS[view]}
          </button>
        ))}
      </div>

      {activeView === "stage" && <StageView dimension={dimension} />}
      {activeView === "transcript" && (
        <TranscriptView dimension={dimension} sharedTranscript={trialState.sharedTranscript} />
      )}
      {activeView === "timeline" && (
        <TimelineView dimension={dimension} sharedTranscript={trialState.sharedTranscript} />
      )}
    </div>
  );
}
