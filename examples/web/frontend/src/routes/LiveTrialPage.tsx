import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge, Group, SegmentedControl, Stack, Tabs, Title } from "@mantine/core";
import { useTrialStore } from "../state/store";
import StageView, { phaseLabel } from "../views/StageView";
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
    const currentStatus = useTrialStore.getState().state.status;
    if ((currentStatus === "done" || currentStatus === "error") && trialId) {
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
    <Stack gap="md" className="live-trial-page">
      <Title order={2}>Trial in progress</Title>

      {trialState.dimensionOrder.length > 1 && (
        <SegmentedControl
          data={trialState.dimensionOrder.map((name) => ({ label: name, value: name }))}
          value={selectedDimension ?? ""}
          onChange={setSelectedDimension}
        />
      )}

      {trialState.dimensionOrder.length > 1 && (
        <Group gap="xs" data-testid="dimension-status-strip">
          {trialState.dimensionOrder
            .filter((name) => name !== selectedDimension)
            .map((name) => (
              <Badge key={name} variant="light" color="gray">
                {name}: {phaseLabel(trialState.dimensions[name])}
              </Badge>
            ))}
        </Group>
      )}

      <Tabs value={activeView} onChange={(value) => setActiveView((value ?? "stage") as ViewName)}>
        <Tabs.List>
          {(Object.keys(VIEW_LABELS) as ViewName[]).map((view) => (
            <Tabs.Tab key={view} value={view}>{VIEW_LABELS[view]}</Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>

      {activeView === "stage" && <StageView dimension={dimension} />}
      {activeView === "transcript" && (
        <TranscriptView dimension={dimension} sharedTranscript={trialState.sharedTranscript} />
      )}
      {activeView === "timeline" && (
        <TimelineView dimension={dimension} sharedTranscript={trialState.sharedTranscript} />
      )}
    </Stack>
  );
}
