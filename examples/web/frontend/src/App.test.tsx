import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "./api/client";
import App from "./App";
import { render, screen } from "./test/render";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("renders the setup page at the root route", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue({
      dimensions: [], presets: [], evaluation_strategies: [], provider_presets: [], env_status: {},
    });
    render(<App />);
    expect(await screen.findByText("New trial")).toBeInTheDocument();
  });

  it("navigates to History via the nav link", async () => {
    vi.spyOn(client, "getCatalog").mockResolvedValue({
      dimensions: [], presets: [], evaluation_strategies: [], provider_presets: [], env_status: {},
    });
    vi.spyOn(client, "listTrials").mockResolvedValue([]);
    render(<App />);
    await screen.findByText("New trial");
    screen.getByRole("link", { name: "History" }).click();
    expect(await screen.findByText("No trials run yet this session.")).toBeInTheDocument();
  });
});
