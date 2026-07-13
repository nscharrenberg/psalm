import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "./api/client";
import App from "./App";

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
});
