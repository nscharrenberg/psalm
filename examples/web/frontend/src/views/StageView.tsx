import { useMemo } from "react";
import { Badge, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconScale } from "@tabler/icons-react";
import type { DimensionState } from "../state/eventReducer";

interface StageViewProps {
  dimension: DimensionState | null;
}

export function phaseLabel(dimension: DimensionState): string {
  if (dimension.phase === "verdict") return `Verdict: ${dimension.verdict}`;
  if (dimension.phase === "deliberation") return `Deliberation — round ${dimension.currentRound}`;
  return `Argumentation — round ${dimension.currentRound}`;
}

const SPEAKING_STYLE = {
  borderColor: "var(--mantine-color-gold-6)",
  boxShadow: "0 0 12px var(--mantine-color-gold-6)",
};

export default function StageView({ dimension }: StageViewProps) {
  if (dimension === null) {
    return <Text c="dimmed" className="stage-empty">Waiting for the trial to begin...</Text>;
  }

  const voteCounts = useMemo(() => Object.values(dimension.jurorVotes).reduce<Record<string, number>>((acc, v) => {
    acc[v.vote] = (acc[v.vote] ?? 0) + 1;
    return acc;
  }, {}), [dimension.jurorVotes]);

  const isJurorSpeaking = dimension.speakingRole !== null
    && dimension.speakingRole !== "prosecution"
    && dimension.speakingRole !== "defense";

  function badgeColor(vote: string): string {
    if (vote === "Guilty") return "red";
    if (vote === "Not Guilty") return "green";
    return "gray";
  }

  return (
    <Stack gap="md" className="stage-view">
      <Title order={4} className="stage-phase-indicator">{phaseLabel(dimension)}</Title>

      <Card withBorder padding="md" data-testid="stage-bench">
        <Group gap="xs">
          <IconScale size={18} />
          <Text fw={600}>Judge</Text>
        </Group>
        {dimension.rejectedArgumentCount > 0 && (
          <Text size="sm" c="dimmed">{dimension.rejectedArgumentCount} objection(s) sustained so far.</Text>
        )}
      </Card>

      <Group grow gap="md">
        <Card
          withBorder padding="md" data-testid="stage-podium-prosecution"
          style={dimension.speakingRole === "prosecution" ? SPEAKING_STYLE : undefined}
        >
          <Text fw={600} size="sm" tt="uppercase" c="dimmed">Prosecutor</Text>
          {dimension.speakingRole === "prosecution" && dimension.latestSpeech && (
            <Text key={dimension.latestSpeech} className="stage-speech stage-speech-pulse" mt="xs">
              &quot;{dimension.latestSpeech}&quot;
            </Text>
          )}
        </Card>
        <Card
          withBorder padding="md" data-testid="stage-podium-defense"
          style={dimension.speakingRole === "defense" ? SPEAKING_STYLE : undefined}
        >
          <Text fw={600} size="sm" tt="uppercase" c="dimmed">Defense</Text>
          {dimension.speakingRole === "defense" && dimension.latestSpeech && (
            <Text key={dimension.latestSpeech} className="stage-speech stage-speech-pulse" mt="xs">
              &quot;{dimension.latestSpeech}&quot;
            </Text>
          )}
        </Card>
      </Group>

      <Card withBorder padding="md" data-testid="stage-jury">
        <Text fw={600} size="sm">Jury ({Object.keys(dimension.jurorVotes).length} voted)</Text>
        <Group gap="xs" mt="xs">
          {Object.entries(voteCounts).map(([vote, count]) => (
            <Badge key={vote} color={badgeColor(vote)} variant="light">{count} × {vote}</Badge>
          ))}
        </Group>
        {isJurorSpeaking && dimension.latestSpeech && (
          <Text key={dimension.latestSpeech} className="stage-speech stage-speech-pulse" mt="xs">
            {dimension.speakingRole}: &quot;{dimension.latestSpeech}&quot;
          </Text>
        )}
      </Card>
    </Stack>
  );
}
