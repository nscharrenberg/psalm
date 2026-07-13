import type { AgentConfigInput, ProviderPreset } from "../api/types";

interface AgentConfigPanelProps {
  label: string;
  config: AgentConfigInput;
  onChange: (config: AgentConfigInput) => void;
  envAvailable: boolean;
  providerPresets: ProviderPreset[];
}

export default function AgentConfigPanel(
  { label, config, onChange, envAvailable, providerPresets }: AgentConfigPanelProps,
) {
  function applyProviderPreset(id: string) {
    const preset = providerPresets.find((p) => p.id === id);
    if (!preset) return;
    onChange({ ...config, base_url: preset.base_url });
  }

  const inputId = label.toLowerCase().replace(/\s+/g, "-");
  const requiredOrEnv = envAvailable ? "✓ using environment variable" : "required";

  return (
    <fieldset className="agent-config-panel">
      <legend>{label}</legend>

      <label htmlFor={`${inputId}-provider`}>Provider</label>
      <select id={`${inputId}-provider`} onChange={(e) => applyProviderPreset(e.target.value)} defaultValue="">
        <option value="" disabled>Choose a provider (optional)</option>
        {providerPresets.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>

      <label htmlFor={`${inputId}-base-url`}>Base URL</label>
      <input
        id={`${inputId}-base-url`}
        type="text"
        value={config.base_url ?? ""}
        onChange={(e) => onChange({ ...config, base_url: e.target.value })}
        placeholder={envAvailable ? "leave blank to use environment variable" : "required"}
      />

      <label htmlFor={`${inputId}-api-key`}>API key</label>
      <input
        id={`${inputId}-api-key`}
        type="password"
        value={config.api_key ?? ""}
        onChange={(e) => onChange({ ...config, api_key: e.target.value })}
        placeholder={requiredOrEnv}
      />

      <label htmlFor={`${inputId}-model`}>Model</label>
      <input
        id={`${inputId}-model`}
        type="text"
        value={config.model ?? ""}
        onChange={(e) => onChange({ ...config, model: e.target.value })}
        placeholder={envAvailable ? "leave blank to use environment variable" : "required"}
      />

      <label htmlFor={`${inputId}-temperature`}>Temperature</label>
      <input
        id={`${inputId}-temperature`}
        type="number"
        step={0.1}
        min={0}
        max={2}
        value={config.temperature ?? ""}
        onChange={(e) => onChange({
          ...config, temperature: e.target.value === "" ? undefined : Number(e.target.value),
        })}
      />
    </fieldset>
  );
}
