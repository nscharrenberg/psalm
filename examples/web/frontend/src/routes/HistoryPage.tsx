import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listTrials } from "../api/client";
import type { TrialSummary } from "../api/types";

export default function HistoryPage() {
  const [trials, setTrials] = useState<TrialSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTrials().then(setTrials).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p role="alert">Failed to load trial history: {error}</p>;
  if (!trials) return <p>Loading...</p>;

  return (
    <div className="history-page">
      <h1>Trial history</h1>
      {trials.length === 0 && <p>No trials run yet this session.</p>}
      <ul>
        {trials.map((trial) => (
          <li key={trial.id}>
            <Link to={trial.status === "running" ? `/trial/${trial.id}` : `/trial/${trial.id}/result`}>
              {trial.created_at} — {trial.status}
              {trial.verdict && ` — ${trial.verdict}`}
            </Link>
            <p>{trial.source_text_preview} → {trial.target_text_preview}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
