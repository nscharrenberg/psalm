import { describe, expect, it, vi } from "vitest";
import AgentConfigPanel from "./AgentConfigPanel";
import { fireEvent, render, screen } from "../test/render";

const providerPresets = [{ id: "openai", label: "OpenAI", base_url: "https://api.openai.com/v1" }];

describe("AgentConfigPanel", () => {
  it("calls onChange when the API key field changes", () => {
    const onChange = vi.fn();
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={onChange} envAvailable={false} providerPresets={providerPresets} />,
    );
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    expect(onChange).toHaveBeenCalledWith({ api_key: "sk-test" });
  });

  it("shows an env-var placeholder on the API key field when available", () => {
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={vi.fn()} envAvailable providerPresets={providerPresets} />,
    );
    expect(screen.getByLabelText("API key")).toHaveAttribute("placeholder", "✓ using environment variable");
  });

  it("shows a required placeholder on the API key field when no env var is available", () => {
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={vi.fn()} envAvailable={false} providerPresets={providerPresets} />,
    );
    expect(screen.getByLabelText("API key")).toHaveAttribute("placeholder", "required");
  });

  it("applying a provider preset fills the base URL", () => {
    const onChange = vi.fn();
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={onChange} envAvailable={false} providerPresets={providerPresets} />,
    );
    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "openai" } });
    expect(onChange).toHaveBeenCalledWith({ base_url: "https://api.openai.com/v1" });
  });

  it("updating the temperature field parses it as a number", () => {
    const onChange = vi.fn();
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={onChange} envAvailable={false} providerPresets={providerPresets} />,
    );
    fireEvent.change(screen.getByLabelText("Temperature"), { target: { value: "0.7" } });
    expect(onChange).toHaveBeenCalledWith({ temperature: 0.7 });
  });

  it("is reachable as an accessible group named after its label", () => {
    render(
      <AgentConfigPanel label="Prosecutor" config={{}} onChange={vi.fn()} envAvailable={false} providerPresets={providerPresets} />,
    );
    expect(screen.getByRole("group", { name: "Prosecutor" })).toBeInTheDocument();
  });
});
