import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Accordion, Badge, Button, Checkbox, Group, NativeSelect, NumberInput,
  Stack, Stepper, Text, Textarea, Title,
} from "@mantine/core";
import { TrialConfigError, TrialConflictError, getCatalog, startTrial } from "../api/client";
import type { AgentConfigInput, CatalogResponse, JurorConfigInput } from "../api/types";
import AgentConfigPanel from "../components/AgentConfigPanel";

function emptyAgentConfig(): AgentConfigInput {
  return {};
}

function emptyJurorConfig(): JurorConfigInput {
  return {};
}

function agentSummary(config: AgentConfigInput, envAvailable: boolean): string {
  const hasOverride = Boolean(
    config.base_url || config.api_key || config.model || config.temperature !== undefined,
  );
  if (hasOverride) return "configured";
  return envAvailable ? "✓ using environment variable" : "required";
}

export default function SetupPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [step, setStep] = useState(0);

  const [sourceText, setSourceText] = useState("");
  const [targetText, setTargetText] = useState("");
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [evaluationStrategy, setEvaluationStrategy] = useState("fully_separate");
  const [argumentationRounds, setArgumentationRounds] = useState(3);
  const [deliberationRounds, setDeliberationRounds] = useState(2);
  const [timeLimitSeconds, setTimeLimitSeconds] = useState(120);
  const [maxConcurrentLlmCalls, setMaxConcurrentLlmCalls] = useState(8);
  const [maxRetries, setMaxRetries] = useState(3);
  const [maxRequestsPerMinute, setMaxRequestsPerMinute] = useState(60);
  const [maxTokensPerMinute, setMaxTokensPerMinute] = useState(40000);
  const [retryAfterFallbackSeconds, setRetryAfterFallbackSeconds] = useState(0);

  const [prosecutor, setProsecutor] = useState<AgentConfigInput>(emptyAgentConfig());
  const [defense, setDefense] = useState<AgentConfigInput>(emptyAgentConfig());
  const [judge, setJudge] = useState<AgentConfigInput>(emptyAgentConfig());
  const [jury, setJury] = useState<JurorConfigInput[]>([
    emptyJurorConfig(), emptyJurorConfig(), emptyJurorConfig(),
  ]);
  const [globalConfig, setGlobalConfig] = useState<AgentConfigInput>(emptyAgentConfig());

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

  function applyGlobalConfigToAllAgents() {
    setProsecutor(globalConfig);
    setDefense(globalConfig);
    setJudge(globalConfig);
    setJury((current) => current.map((j) => ({ ...globalConfig, seed: j.seed })));
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
        max_concurrent_llm_calls: maxConcurrentLlmCalls,
        max_retries: maxRetries,
        max_requests_per_minute: maxRequestsPerMinute,
        max_tokens_per_minute: maxTokensPerMinute,
        retry_after_fallback_seconds: retryAfterFallbackSeconds,
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
    return <Text role="alert" c="red">Failed to load configuration options: {catalogError}</Text>;
  }
  if (!catalog) {
    return <Text>Loading...</Text>;
  }

  const canSubmit = (
    sourceText.trim() !== "" && targetText.trim() !== "" && selectedDimensions.length > 0 && !submitting
  );

  const agentPanels = [
    { label: "Prosecutor", config: prosecutor, onChange: setProsecutor, envKey: "PSALM_PROSECUTOR_API_KEY" },
    { label: "Defense", config: defense, onChange: setDefense, envKey: "PSALM_DEFENSE_API_KEY" },
    { label: "Judge", config: judge, onChange: setJudge, envKey: "PSALM_JUDGE_API_KEY" },
  ] as const;

  return (
    <Stack gap="lg" className="setup-page">
      <Title order={2}>New trial</Title>

      <Stepper active={step} onStepClick={setStep} allowNextStepsSelect={false}>
        <Stepper.Step label="Text">
          <Stack gap="sm" mt="md">
            <NativeSelect
              id="preset-select" label="Preset"
              data={[
                { value: "", label: "Choose a preset (optional)" },
                ...catalog.presets.map((p) => ({ value: p.id, label: p.label })),
              ]}
              onChange={(e) => applyPreset(e.target.value)}
            />
            <Textarea
              id="source-text" label="Source text" value={sourceText}
              onChange={(e) => setSourceText(e.target.value)} minRows={6} autosize
            />
            <Textarea
              id="target-text" label="Target text" value={targetText}
              onChange={(e) => setTargetText(e.target.value)} minRows={6} autosize
            />
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Dimensions">
          <Stack gap="lg" mt="md">
            {(["infringement", "exception"] as const).map((type) => (
              <div key={type}>
                <Text fw={600} mb="xs">
                  {type === "infringement" ? "Infringement dimensions" : "Exception dimensions"}
                </Text>
                <Stack gap="xs">
                  {catalog.dimensions.filter((d) => d.dimension_type === type).map((d) => (
                    <Checkbox
                      key={d.name} label={d.name} title={d.description}
                      checked={selectedDimensions.includes(d.name)}
                      onChange={() => toggleDimension(d.name)}
                    />
                  ))}
                </Stack>
              </div>
            ))}

            <Accordion>
              <Accordion.Item value="advanced">
                <Accordion.Control>Advanced settings</Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="sm">
                    <NativeSelect
                      id="strategy-select" label="Evaluation strategy" value={evaluationStrategy}
                      data={catalog.evaluation_strategies.map((s) => ({ value: s.value, label: s.label }))}
                      onChange={(e) => setEvaluationStrategy(e.target.value)}
                    />
                    <NumberInput
                      id="argumentation-rounds" label="Argumentation rounds" min={1}
                      value={argumentationRounds}
                      onChange={(value) => setArgumentationRounds(Number(value))}
                    />
                    <NumberInput
                      id="deliberation-rounds" label="Deliberation rounds" min={1}
                      value={deliberationRounds}
                      onChange={(value) => setDeliberationRounds(Number(value))}
                    />
                    <NumberInput
                      id="time-limit" label="Time limit (seconds)" min={1}
                      value={timeLimitSeconds}
                      onChange={(value) => setTimeLimitSeconds(Number(value))}
                    />
                    <NumberInput
                      id="max-concurrent-llm-calls" label="Max concurrent LLM calls" min={1}
                      value={maxConcurrentLlmCalls}
                      onChange={(value) => setMaxConcurrentLlmCalls(Number(value))}
                    />
                    <NumberInput
                      id="max-retries" label="Max retries" min={1}
                      value={maxRetries}
                      onChange={(value) => setMaxRetries(Number(value))}
                    />
                    <NumberInput
                      id="max-requests-per-minute" label="Max requests per minute (0 = unlimited)" min={0}
                      value={maxRequestsPerMinute}
                      onChange={(value) => setMaxRequestsPerMinute(Number(value))}
                    />
                    <NumberInput
                      id="max-tokens-per-minute" label="Max tokens per minute (0 = unlimited)" min={0}
                      value={maxTokensPerMinute}
                      onChange={(value) => setMaxTokensPerMinute(Number(value))}
                    />
                    <NumberInput
                      id="retry-after-fallback-seconds"
                      label="Retry-After fallback (seconds, 0 = disabled)" min={0}
                      value={retryAfterFallbackSeconds}
                      onChange={(value) => setRetryAfterFallbackSeconds(Number(value))}
                    />
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Agents">
          <Stack gap="md" mt="md">
            <Accordion>
              <Accordion.Item value="global-defaults">
                <Accordion.Control>Set one configuration for all agents</Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="sm">
                    <AgentConfigPanel
                      label="Global defaults" config={globalConfig} onChange={setGlobalConfig}
                      envAvailable={catalog.env_status.PSALM_API_KEY}
                      providerPresets={catalog.provider_presets}
                    />
                    <Button variant="light" onClick={applyGlobalConfigToAllAgents}>Apply to all agents</Button>
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
            <Accordion multiple defaultValue={[]}>
              {agentPanels.map((agent) => (
                <Accordion.Item key={agent.label} value={agent.label}>
                  <Accordion.Control>
                    <Group justify="space-between" pr="md">
                      <Text>{agent.label}</Text>
                      <Badge variant="light" color="gray">
                        {agentSummary(
                          agent.config,
                          catalog.env_status[agent.envKey] || catalog.env_status.PSALM_API_KEY,
                        )}
                      </Badge>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <AgentConfigPanel
                      label={agent.label} config={agent.config} onChange={agent.onChange}
                      envAvailable={catalog.env_status[agent.envKey] || catalog.env_status.PSALM_API_KEY}
                      providerPresets={catalog.provider_presets}
                    />
                  </Accordion.Panel>
                </Accordion.Item>
              ))}

              {jury.map((jurorConfig, index) => (
                <Accordion.Item key={index} value={`Juror ${index}`}>
                  <Accordion.Control>
                    <Group justify="space-between" pr="md">
                      <Text>Juror {index}</Text>
                      <Badge variant="light" color="gray">
                        {agentSummary(
                          jurorConfig,
                          catalog.env_status.PSALM_JURY_API_KEY || catalog.env_status.PSALM_API_KEY,
                        )}
                      </Badge>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <Stack gap="sm">
                      <AgentConfigPanel
                        label={`Juror ${index}`} config={jurorConfig}
                        onChange={(updated) => setJury((current) => (
                          current.map((j, i) => (i === index ? { ...updated, seed: j.seed } : j))
                        ))}
                        envAvailable={catalog.env_status.PSALM_JURY_API_KEY || catalog.env_status.PSALM_API_KEY}
                        providerPresets={catalog.provider_presets}
                      />
                      {jury.length > 3 && (
                        <Button variant="subtle" color="red" onClick={() => removeJuror(index)}>
                          Remove juror {index}
                        </Button>
                      )}
                    </Stack>
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
            <Button variant="light" onClick={addJuror}>Add juror</Button>
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Review">
          <Stack gap="md" mt="md">
            <div>
              <Text fw={600}>Source text</Text>
              <Text size="sm" c="dimmed">{sourceText || "(empty)"}</Text>
            </div>
            <div>
              <Text fw={600}>Target text</Text>
              <Text size="sm" c="dimmed">{targetText || "(empty)"}</Text>
            </div>
            <div>
              <Text fw={600}>Dimensions</Text>
              <Text size="sm" c="dimmed">
                {selectedDimensions.length > 0 ? selectedDimensions.join(", ") : "(none selected)"}
              </Text>
            </div>
            {submitError && <Text role="alert" c="red">{submitError}</Text>}
            <Button onClick={handleSubmit} disabled={!canSubmit}>
              {submitting ? "Starting..." : "Start Trial"}
            </Button>
          </Stack>
        </Stepper.Step>
      </Stepper>

      <Group justify="space-between">
        <Button variant="default" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>
          Back
        </Button>
        {step < 3 && (
          <Button onClick={() => setStep((s) => Math.min(3, s + 1))}>Next</Button>
        )}
      </Group>
    </Stack>
  );
}
