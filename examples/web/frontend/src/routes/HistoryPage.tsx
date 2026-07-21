import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Anchor, Badge, Stack, Table, Text, Title } from "@mantine/core";
import { listTrials } from "../api/client";
import type { TrialSummary } from "../api/types";

function statusColor(status: string): string {
  if (status === "done") return "green";
  if (status === "error") return "red";
  return "gold";
}

export default function HistoryPage() {
  const [trials, setTrials] = useState<TrialSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTrials().then(setTrials).catch((e) => setError(String(e)));
  }, []);

  if (error) return <Text role="alert" c="red">Failed to load trial history: {error}</Text>;
  if (!trials) return <Text>Loading...</Text>;

  return (
    <Stack gap="md" className="history-page">
      <Title order={2}>Trial history</Title>
      {trials.length === 0 && <Text>No trials run yet this session.</Text>}
      {trials.length > 0 && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Created</Table.Th><Table.Th>Status</Table.Th><Table.Th>Verdict</Table.Th><Table.Th>Texts</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {trials.map((trial) => (
              <Table.Tr key={trial.id}>
                <Table.Td>
                  <Anchor
                    component={Link}
                    to={trial.status === "running" ? `/trial/${trial.id}` : `/trial/${trial.id}/result`}
                  >
                    {trial.created_at}
                  </Anchor>
                </Table.Td>
                <Table.Td><Badge color={statusColor(trial.status)} variant="light">{trial.status}</Badge></Table.Td>
                <Table.Td>{trial.verdict ?? "—"}</Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">{trial.source_text_preview} → {trial.target_text_preview}</Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
