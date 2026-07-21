import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  ActionIcon, Alert, Accordion, Badge, Button, Group, Slider, Stack, Table, Text, Title,
} from "@mantine/core";
import { IconPlayerPause, IconPlayerPlay } from "@tabler/icons-react";
import { fetchTrialEvents, getTrial } from "../api/client";
import type { TrialDetail } from "../api/types";
import { useTrialStore } from "../state/store";
import StageView from "../views/StageView";

export default function ResultsPage() {
  const { trialId } = useParams<{ trialId: string }>();
  const [detail, setDetail] = useState<TrialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showReplay, setShowReplay] = useState(false);
  const [replayDimension, setReplayDimension] = useState<string | null>(null);
  const [isLoadingReplay, setIsLoadingReplay] = useState(false);

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
    if (liveTrialId === trialId && liveEvents.length > 0) {
      // Fast path: the trial we just watched live is still buffered — no need
      // to round-trip to the server for events we already have.
      loadForReplay(liveEvents);
      setShowReplay(true);
      return;
    }
    if (!trialId) return;
    setIsLoadingReplay(true);
    fetchTrialEvents(trialId).then((events) => {
      loadForReplay(events);
      setShowReplay(true);
      setIsLoadingReplay(false);
    });
  }

  if (error) return <Alert role="alert" color="red">Failed to load trial: {error}</Alert>;
  if (!detail) return <Text>Loading...</Text>;

  const result = detail.result;

  function verdictColor(verdict: string): string {
    if (verdict === "Guilty") return "red";
    if (verdict === "Not Guilty") return "green";
    return "gray";
  }

  // Exception dimensions ("Scènes à Faire" etc.) aren't guilty of anything — they discount
  // the infringement score when they apply. Their Guilty/Not Guilty verdict is a legal-vote
  // label under the hood (unchanged), but shown to users as "applies"/"does not apply".
  function dimensionVerdictLabel(dv: { dimension_type: string; verdict: string }): string {
    if (dv.dimension_type !== "exception") return dv.verdict;
    if (dv.verdict === "Guilty") return "Exception Applies";
    if (dv.verdict === "Not Guilty") return "Exception Does Not Apply";
    return dv.verdict;
  }

  function dimensionVerdictColor(dv: { dimension_type: string; verdict: string }): string {
    if (dv.dimension_type === "exception") return "blue";
    return verdictColor(dv.verdict);
  }

  return (
    <Stack gap="lg" className="results-page">
      <Title order={2}>Trial result</Title>
      {detail.status === "error" && (
        <Alert role="alert" color="red">Trial failed: {detail.error_message}</Alert>
      )}

      {result && (
        <>
          <Alert color={verdictColor(result.verdict)} title={`Verdict: ${result.verdict}`} className="verdict-banner">
            {result.rationale}
          </Alert>

          <Stack gap="sm">
            <Title order={4}>Per-dimension breakdown</Title>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Dimension</Table.Th><Table.Th>Type</Table.Th><Table.Th>Importance</Table.Th>
                  <Table.Th>Verdict</Table.Th><Table.Th>Score</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {result.dimension_verdicts.map((dv) => (
                  <Table.Tr key={dv.dimension}>
                    <Table.Td>{dv.dimension}</Table.Td>
                    <Table.Td>{dv.dimension_type}</Table.Td>
                    <Table.Td>{dv.importance}</Table.Td>
                    <Table.Td>
                      <Badge color={dimensionVerdictColor(dv)} variant="light">{dimensionVerdictLabel(dv)}</Badge>
                    </Table.Td>
                    <Table.Td>{dv.weighted_score.toFixed(2)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Stack>

          <Accordion>
            {result.dimension_verdicts.map((dv) => (
              <Accordion.Item key={dv.dimension} value={dv.dimension}>
                <Accordion.Control>{dv.dimension} — full log</Accordion.Control>
                <Accordion.Panel>
                  <Title order={5}>Argumentation</Title>
                  {dv.argumentation_log.rounds.map((round) => (
                    <div key={round.round}>
                      <Text fw={600} size="sm" mt="sm">Round {round.round}</Text>
                      {round.prosecution_arguments.map((arg, i) => <Text key={`pa${i}`} size="sm">Prosecution: {arg.claim}</Text>)}
                      {round.prosecution_rejected_arguments.map((rej, i) => (
                        <Text key={`pr${i}`} size="sm" c="dimmed">Rejected (prosecution): {rej.argument.claim} — {rej.rejection_reason}</Text>
                      ))}
                      {round.defense_counters.map((arg, i) => <Text key={`dc${i}`} size="sm">Defense counters: {arg.claim}</Text>)}
                      {round.defense_counter_rejected_arguments.map((rej, i) => (
                        <Text key={`dcr${i}`} size="sm" c="dimmed">Rejected (defense counter): {rej.argument.claim} — {rej.rejection_reason}</Text>
                      ))}
                      {round.defense_arguments.map((arg, i) => <Text key={`da${i}`} size="sm">Defense: {arg.claim}</Text>)}
                      {round.defense_rejected_arguments.map((rej, i) => (
                        <Text key={`dr${i}`} size="sm" c="dimmed">Rejected (defense): {rej.argument.claim} — {rej.rejection_reason}</Text>
                      ))}
                      {round.prosecution_counters.map((arg, i) => (
                        <Text key={`pc${i}`} size="sm">Prosecution counters: {arg.claim}</Text>
                      ))}
                      {round.prosecution_counter_rejected_arguments.map((rej, i) => (
                        <Text key={`pcr${i}`} size="sm" c="dimmed">Rejected (prosecution counter): {rej.argument.claim} — {rej.rejection_reason}</Text>
                      ))}
                    </div>
                  ))}
                  {dv.argumentation_log.prosecution_closing_argument && (
                    <Text size="sm" mt="sm">Prosecution closing: {dv.argumentation_log.prosecution_closing_argument}</Text>
                  )}
                  {dv.argumentation_log.defense_closing_argument && (
                    <Text size="sm">Defense closing: {dv.argumentation_log.defense_closing_argument}</Text>
                  )}

                  <Title order={5} mt="md">Deliberation</Title>
                  {dv.debate_log.rounds.map((round) => (
                    <div key={round.round}>
                      <Text fw={600} size="sm" mt="sm">Round {round.round}</Text>
                      {round.votes.map((vote) => (
                        <Text key={vote.juror_id} size="sm">{vote.juror_id}: {vote.vote} — {vote.rationale}</Text>
                      ))}
                      {round.discussion_messages.map((msg, i) => (
                        <Text key={i} size="sm">{msg.juror_id}: {msg.message}</Text>
                      ))}
                    </div>
                  ))}
                </Accordion.Panel>
              </Accordion.Item>
            ))}
          </Accordion>
        </>
      )}

      {detail.status !== "running" && !showReplay && (
        <Button onClick={startReplay} disabled={isLoadingReplay} variant="light">
          {isLoadingReplay ? "Loading replay..." : "Replay this trial"}
        </Button>
      )}

      {showReplay && replayMode === "replay" && (
        <Stack gap="sm" className="replay-section">
          <Title order={4}>Replay</Title>
          {replayState.dimensionOrder.length > 1 && (
            <Group gap="xs" className="dimension-selector">
              {replayState.dimensionOrder.map((name) => (
                <Badge
                  key={name} variant={name === replayDimension ? "filled" : "light"}
                  color="gold" style={{ cursor: "pointer" }}
                  onClick={() => setReplayDimension(name)}
                >
                  {name}
                </Badge>
              ))}
            </Group>
          )}
          <Group gap="sm" align="center" className="replay-controls">
            <ActionIcon
              onClick={isPlaying ? pause : play} variant="filled" size="lg"
              aria-label={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? <IconPlayerPause size={18} /> : <IconPlayerPlay size={18} />}
            </ActionIcon>
            <Slider
              style={{ flex: 1 }}
              min={-1} max={Math.max(liveEvents.length - 1, 0)} value={replayIndex}
              onChange={scrubTo} label={null}
            />
          </Group>
          <StageView dimension={replayDimension ? replayState.dimensions[replayDimension] ?? null : null} />
        </Stack>
      )}
    </Stack>
  );
}
