import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor, within } from "../test/render";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { CatalogResponse } from "../api/types";
import SetupPage from "./SetupPage";

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
  it("loads the catalog and shows Character as a selectable dimension", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    expect(await screen.findByLabelText("Character")).toBeInTheDocument();
  });

  it("applying a preset fills the source and target text fields", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByLabelText("Character");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    expect(screen.getByLabelText("Source text")).toHaveValue("SRC");
    expect(screen.getByLabelText("Target text")).toHaveValue("TGT");
  });

  it("disables Start Trial until source, target, and at least one dimension are set", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByText("Agents");
    expect(screen.getByText("Start Trial")).toBeDisabled();
  });

  it("submits the trial with the right payload and navigates on success", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    const startTrialSpy = vi.spyOn(client, "startTrial").mockResolvedValue({ trial_id: "abc" });
    renderSetupPage();
    await screen.findByLabelText("Character");

    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    fireEvent.click(screen.getByLabelText("Character"));
    fireEvent.click(screen.getByText("Start Trial"));

    await waitFor(() => expect(startTrialSpy).toHaveBeenCalled());
    const payload = startTrialSpy.mock.calls[0][0];
    expect(payload.source_text).toBe("SRC");
    expect(payload.dimensions).toContain("Character");
  });

  it("shows an error message when the backend reports a config error", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    vi.spyOn(client, "startTrial").mockRejectedValue(
      new client.TrialConfigError("PSALM-WEB-001", "No API key provided.", {}),
    );
    renderSetupPage();
    await screen.findByLabelText("Character");
    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "infringing" } });
    fireEvent.click(screen.getByLabelText("Character"));
    fireEvent.click(screen.getByText("Start Trial"));

    expect(await screen.findByRole("alert")).toHaveTextContent("No API key provided.");
  });

  it("falls back to the generic env var when a role-specific env var is unset", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue({
      ...fakeCatalog,
      env_status: { PSALM_API_KEY: true, PSALM_PROSECUTOR_API_KEY: false },
    });
    renderSetupPage();
    await screen.findByLabelText("Character");

    const prosecutorPanel = screen.getByRole("group", { name: "Prosecutor" });
    expect(within(prosecutorPanel).getByLabelText("API key")).toHaveAttribute(
      "placeholder", "✓ using environment variable",
    );
  });

  it("adds and removes jurors, never going below 3", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue(fakeCatalog);
    renderSetupPage();
    await screen.findByText("Jury");
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(3);
    expect(screen.queryByText("Remove juror 0")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Add juror"));
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(4);
    expect(screen.getByText("Remove juror 3")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Remove juror 3"));
    expect(screen.getAllByText(/^Juror \d$/)).toHaveLength(3);
  });
});
