import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { CatalogResponse } from "../api/types";
import SetupPage from "./SetupPage";
import { fireEvent, render, screen, waitFor, within } from "../test/render";

const fakeCatalog = {
  dimensions: [
    { name: "Character", dimension_type: "infringement" as const, importance: "high", description: "d", sub_dimensions: [] },
    { name: "Scenes a Faire", dimension_type: "exception" as const, importance: "medium", description: "d", sub_dimensions: [] },
  ],
  presets: [{ id: "infringing", label: "Infringing example", source_text: "SRC", target_text: "TGT" }],
  evaluation_strategies: [{ value: "fully_separate", label: "Fully separate", description: "d" }],
  provider_presets: [{ id: "openai", label: "OpenAI", base_url: "https://api.openai.com/v1" }],
  env_status: { PSALM_API_KEY: true },
} as const satisfies CatalogResponse;

afterEach(() => {
  vi.restoreAllMocks();
});

function renderSetupPage() {
  return render(
    <MemoryRouter>
      <SetupPage />
    </MemoryRouter>,
  );
}

describe("SetupPage", () => {
  it("loads the catalog and shows the Text step first", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    expect(await screen.findByLabelText("Preset")).toBeInTheDocument();
    expect(screen.queryByLabelText("Character")).not.toBeInTheDocument();
  });

  it("applying a preset fills the source and target text fields", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    expect(screen.getByLabelText("Source text")).toHaveValue("SRC");
    expect(screen.getByLabelText("Target text")).toHaveValue("TGT");
  });

  it("advancing to the Dimensions step shows selectable dimensions", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    expect(await screen.findByLabelText("Character")).toBeInTheDocument();
    expect(screen.getByLabelText("Scenes a Faire")).toBeInTheDocument();
  });

  it("advancing to the Agents step shows each agent's env-var status as a badge", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    // Accordion.Control is queried by role, not by text: Mantine's Accordion.Panel content
    // (which contains AgentConfigPanel's Fieldset, whose legend also reads "Prosecutor")
    // stays mounted-but-hidden when collapsed, so a plain text query would be ambiguous.
    const prosecutorControl = await screen.findByRole("button", { name: /Prosecutor/ });
    expect(within(prosecutorControl).getByText("✓ using environment variable")).toBeInTheDocument();
  });

  it("expanding an agent panel reveals its configuration fields", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    const prosecutorControl = await screen.findByRole("button", { name: /Prosecutor/ });
    fireEvent.click(prosecutorControl);
    const prosecutorGroup = await screen.findByRole("group", { name: "Prosecutor" });
    expect(within(prosecutorGroup).getByLabelText("API key")).toBeInTheDocument();
  });

  it("adds and removes jurors, never going below 3", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    await screen.findByRole("button", { name: /^Juror 0/ });
    expect(screen.getAllByRole("button", { name: /^Juror \d/ })).toHaveLength(3);

    fireEvent.click(screen.getByText("Add juror"));
    expect(screen.getAllByRole("button", { name: /^Juror \d/ })).toHaveLength(4);

    fireEvent.click(screen.getByRole("button", { name: /^Juror 3/ }));
    fireEvent.click(await screen.findByText("Remove juror 3"));
    expect(screen.getAllByRole("button", { name: /^Juror \d/ })).toHaveLength(3);
  });

  it("disables Start Trial until source, target, and at least one dimension are set", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    // Mantine's Button wraps its label in an inner <span>, so a text query would
    // return that span rather than the disabled <button> itself; query by role instead.
    expect(await screen.findByRole("button", { name: "Start Trial" })).toBeDisabled();
  });

  it("submits the trial with the right payload and navigates on success", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    const startTrialSpy = vi.spyOn(client, "startTrial").mockResolvedValue({ trial_id: "abc" });
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByLabelText("Character"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Start Trial"));

    await waitFor(() => expect(startTrialSpy).toHaveBeenCalled());
    const payload = startTrialSpy.mock.calls[0][0];
    expect(payload.source_text).toBe("SRC");
    expect(payload.dimensions).toContain("Character");
    expect(payload.max_concurrent_llm_calls).toBe(8);
    expect(payload.max_retries).toBe(3);
  });

  it("shows an error message when the backend reports a config error", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    vi.spyOn(client, "startTrial").mockRejectedValue(
      new client.TrialConfigError("PSALM-WEB-001", "No API key provided.", {}),
    );
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByLabelText("Character"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Start Trial"));

    expect(await screen.findByRole("alert")).toHaveTextContent("No API key provided.");
  });

  it("falls back to the generic env var when a role-specific env var is unset", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue({
      ...fakeCatalog,
      env_status: { PSALM_API_KEY: true, PSALM_PROSECUTOR_API_KEY: false },
    });
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    const prosecutorControl = await screen.findByRole("button", { name: /Prosecutor/ });
    expect(within(prosecutorControl).getByText("✓ using environment variable")).toBeInTheDocument();
  });

  it("shows a collapsible global defaults panel, collapsed by default", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));

    const globalControl = await screen.findByRole(
      "button", { name: "Set one configuration for all agents" },
    );
    expect(globalControl).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(globalControl);
    expect(globalControl).toHaveAttribute("aria-expanded", "true");
  });

  it("filling the global defaults panel and clicking Apply to all agents propagates it to every agent", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));

    const globalControl = await screen.findByRole(
      "button", { name: "Set one configuration for all agents" },
    );
    fireEvent.click(globalControl);
    const globalGroup = await screen.findByRole("group", { name: "Global defaults" });
    fireEvent.change(within(globalGroup).getByLabelText("API key"), { target: { value: "sk-global" } });
    fireEvent.change(within(globalGroup).getByLabelText("Model"), { target: { value: "gpt-4o-mini" } });
    fireEvent.click(screen.getByText("Apply to all agents"));

    const prosecutorControl = screen.getByRole("button", { name: /Prosecutor/ });
    fireEvent.click(prosecutorControl);
    const prosecutorGroup = await screen.findByRole("group", { name: "Prosecutor" });
    expect(within(prosecutorGroup).getByLabelText("API key")).toHaveValue("sk-global");
    expect(within(prosecutorGroup).getByLabelText("Model")).toHaveValue("gpt-4o-mini");

    const juror0Control = screen.getByRole("button", { name: /^Juror 0/ });
    fireEvent.click(juror0Control);
    const juror0Group = await screen.findByRole("group", { name: "Juror 0" });
    expect(within(juror0Group).getByLabelText("API key")).toHaveValue("sk-global");
  });

  it("a juror added after Apply to all agents was clicked starts blank", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Preset");
    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));

    const globalControl = await screen.findByRole(
      "button", { name: "Set one configuration for all agents" },
    );
    fireEvent.click(globalControl);
    const globalGroup = await screen.findByRole("group", { name: "Global defaults" });
    fireEvent.change(within(globalGroup).getByLabelText("API key"), { target: { value: "sk-global" } });
    fireEvent.click(screen.getByText("Apply to all agents"));

    fireEvent.click(screen.getByText("Add juror"));
    const juror3Control = screen.getByRole("button", { name: /^Juror 3/ });
    fireEvent.click(juror3Control);
    const juror3Group = await screen.findByRole("group", { name: "Juror 3" });
    expect(within(juror3Group).getByLabelText("API key")).toHaveValue("");
  });
});
