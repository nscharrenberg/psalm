import { Fieldset, NativeSelect, NumberInput, PasswordInput, Stack, TextInput } from "@mantine/core";
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
  const envOrRequired = envAvailable ? "leave blank to use environment variable" : "required";

  return (
    <Fieldset legend={label}>
      <Stack gap="sm">
        <NativeSelect
          id={`${inputId}-provider`}
          label="Provider"
          data={[{ value: "", label: "Choose a provider (optional)" }, ...providerPresets.map((p) => ({ value: p.id, label: p.label }))]}
          onChange={(e) => applyProviderPreset(e.target.value)}
        />
        <TextInput
          id={`${inputId}-base-url`}
          label="Base URL"
          value={config.base_url ?? ""}
          onChange={(e) => onChange({ ...config, base_url: e.target.value })}
          placeholder={envOrRequired}
        />
        <PasswordInput
          id={`${inputId}-api-key`}
          label="API key"
          value={config.api_key ?? ""}
          onChange={(e) => onChange({ ...config, api_key: e.target.value })}
          placeholder={requiredOrEnv}
        />
        <TextInput
          id={`${inputId}-model`}
          label="Model"
          value={config.model ?? ""}
          onChange={(e) => onChange({ ...config, model: e.target.value })}
          placeholder={envOrRequired}
        />
        <NumberInput
          id={`${inputId}-temperature`}
          label="Temperature"
          step={0.1}
          min={0}
          max={2}
          value={config.temperature ?? ""}
          onChange={(value) => onChange({
            ...config, temperature: value === "" ? undefined : Number(value),
          })}
        />
      </Stack>
    </Fieldset>
  );
}
