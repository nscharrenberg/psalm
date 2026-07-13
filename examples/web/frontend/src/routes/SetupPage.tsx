import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TrialConfigError, TrialConflictError, getCatalog, startTrial } from "../api/client";
import type { AgentConfigInput, CatalogResponse, JurorConfigInput } from "../api/types";
import AgentConfigPanel from "../components/AgentConfigPanel";

function emptyAgentConfig(): AgentConfigInput {
  return {};
}

function emptyJurorConfig(): JurorConfigInput {
  return {};
}

export default function SetupPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const [sourceText, setSourceText] = useState("");
  const [targetText, setTargetText] = useState("");
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [evaluationStrategy, setEvaluationStrategy] = useState("fully_separate");
  const [argumentationRounds, setArgumentationRounds] = useState(3);
  const [deliberationRounds, setDeliberationRounds] = useState(2);
  const [timeLimitSeconds, setTimeLimitSeconds] = useState(120);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [prosecutor, setProsecutor] = useState<AgentConfigInput>(emptyAgentConfig());
  const [defense, setDefense] = useState<AgentConfigInput>(emptyAgentConfig());
  const [judge, setJudge] = useState<AgentConfigInput>(emptyAgentConfig());
  const [jury, setJury] = useState<JurorConfigInput[]>([
    emptyJurorConfig(), emptyJurorConfig(), emptyJurorConfig(),
  ]);

  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getCatalog().then(setCatalog).catch((e) => setCatalogError(String(e)));
  }, []);

  function applyPreset(presetId: string) {
    const preset = catalog?.presets.find((p) => p.id === presetId);
    if (!preset) return;
    setSourceText(preset.source_text);
    setTargetText(preset.target_text);
  }

  function toggleDimension(name: string) {
    setSelectedDimensions((current) => (
      current.includes(name) ? current.filter((d) => d !== name) : [...current, name]
    ));
  }

  function addJuror() {
    setJury((current) => [...current, emptyJurorConfig()]);
  }

  function removeJuror(index: number) {
    setJury((current) => (current.length <= 3 ? current : current.filter((_, i) => i !== index)));
  }

  async function handleSubmit() {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const { trial_id } = await startTrial({
        source_text: sourceText,
        target_text: targetText,
        dimensions: selectedDimensions,
        evaluation_strategy: evaluationStrategy,
        argumentation_rounds: argumentationRounds,
        deliberation_rounds: deliberationRounds,
        time_limit_seconds: timeLimitSeconds,
        prosecutor,
        defense,
        judge,
        jury,
      });
      navigate(`/trial/${trial_id}`);
    } catch (error) {
      if (error instanceof TrialConflictError) {
        setSubmitError("A trial is already in progress. Watch it, or wait for it to finish.");
      } else if (error instanceof TrialConfigError) {
        setSubmitError(`${error.code}: ${error.message}`);
      } else {
        setSubmitError(String(error));
      }
      setSubmitting(false);
    }
  }

  if (catalogError) {
    return <p role="alert">Failed to load configuration options: {catalogError}</p>;
  }
  if (!catalog) {
    return <p>Loading...</p>;
  }

  const canSubmit = (
    sourceText.trim() !== "" && targetText.trim() !== "" && selectedDimensions.length > 0 && !submitting
  );

  return (
    <div className="setup-page">
      <h1>New trial</h1>

      <section>
        <h2>Texts</h2>
        <label htmlFor="preset-select">Preset</label>
        <select id="preset-select" onChange={(e) => applyPreset(e.target.value)} defaultValue="">
          <option value="" disabled>Choose a preset (optional)</option>
          {catalog.presets.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        <label htmlFor="source-text">Source text</label>
        <textarea id="source-text" value={sourceText} onChange={(e) => setSourceText(e.target.value)} rows={6} />
        <label htmlFor="target-text">Target text</label>
        <textarea id="target-text" value={targetText} onChange={(e) => setTargetText(e.target.value)} rows={6} />
      </section>

      <section>
        <h2>Dimensions</h2>
        {(["infringement", "exception"] as const).map((type) => (
          <div key={type}>
            <h3>{type === "infringement" ? "Infringement dimensions" : "Exception dimensions"}</h3>
            {catalog.dimensions.filter((d) => d.dimension_type === type).map((d) => (
              <label key={d.name} title={d.description}>
                <input
                  type="checkbox"
                  checked={selectedDimensions.includes(d.name)}
                  onChange={() => toggleDimension(d.name)}
                />
                {d.name}
              </label>
            ))}
          </div>
        ))}
      </section>

      <section>
        <button type="button" onClick={() => setAdvancedOpen((v) => !v)}>
          {advancedOpen ? "Hide" : "Show"} advanced settings
        </button>
        {advancedOpen && (
          <div>
            <label htmlFor="strategy-select">Evaluation strategy</label>
            <select
              id="strategy-select" value={evaluationStrategy}
              onChange={(e) => setEvaluationStrategy(e.target.value)}
            >
              {catalog.evaluation_strategies.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <label htmlFor="argumentation-rounds">Argumentation rounds</label>
            <input
              id="argumentation-rounds" type="number" min={1} value={argumentationRounds}
              onChange={(e) => setArgumentationRounds(Number(e.target.value))}
            />
            <label htmlFor="deliberation-rounds">Deliberation rounds</label>
            <input
              id="deliberation-rounds" type="number" min={1} value={deliberationRounds}
              onChange={(e) => setDeliberationRounds(Number(e.target.value))}
            />
            <label htmlFor="time-limit">Time limit (seconds)</label>
            <input
              id="time-limit" type="number" min={1} value={timeLimitSeconds}
              onChange={(e) => setTimeLimitSeconds(Number(e.target.value))}
            />
          </div>
        )}
      </section>

      <section>
        <h2>Agents</h2>
        <AgentConfigPanel
          label="Prosecutor" config={prosecutor} onChange={setProsecutor}
          envAvailable={catalog.env_status.PSALM_PROSECUTOR_API_KEY ?? catalog.env_status.PSALM_API_KEY}
          providerPresets={catalog.provider_presets}
        />
        <AgentConfigPanel
          label="Defense" config={defense} onChange={setDefense}
          envAvailable={catalog.env_status.PSALM_DEFENSE_API_KEY ?? catalog.env_status.PSALM_API_KEY}
          providerPresets={catalog.provider_presets}
        />
        <AgentConfigPanel
          label="Judge" config={judge} onChange={setJudge}
          envAvailable={catalog.env_status.PSALM_JUDGE_API_KEY ?? catalog.env_status.PSALM_API_KEY}
          providerPresets={catalog.provider_presets}
        />

        <h3>Jury</h3>
        {jury.map((jurorConfig, index) => (
          <div key={index}>
            <AgentConfigPanel
              label={`Juror ${index}`} config={jurorConfig}
              onChange={(updated) => setJury((current) => (
                current.map((j, i) => (i === index ? { ...updated, seed: j.seed } : j))
              ))}
              envAvailable={catalog.env_status.PSALM_JURY_API_KEY ?? catalog.env_status.PSALM_API_KEY}
              providerPresets={catalog.provider_presets}
            />
            {jury.length > 3 && (
              <button type="button" onClick={() => removeJuror(index)}>Remove juror {index}</button>
            )}
          </div>
        ))}
        <button type="button" onClick={addJuror}>Add juror</button>
      </section>

      {submitError && <p role="alert">{submitError}</p>}
      <button type="button" onClick={handleSubmit} disabled={!canSubmit}>
        {submitting ? "Starting..." : "Start Trial"}
      </button>
    </div>
  );
}
