import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import HistoryPage from "./HistoryPage";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HistoryPage", () => {
  it("shows a message when there are no trials yet", async () => {
    vi.spyOn(client, "listTrials").mockResolvedValue([]);
    render(<MemoryRouter><HistoryPage /></MemoryRouter>);
    expect(await screen.findByText("No trials run yet this session.")).toBeInTheDocument();
  });

  it("lists each trial with its status and verdict", async () => {
    vi.spyOn(client, "listTrials").mockResolvedValue([
      {
        id: "abc", created_at: "2026-01-01T00:00:00Z", status: "done",
        source_text_preview: "s", target_text_preview: "t", verdict: "Guilty", error_message: null,
      },
    ]);
    render(<MemoryRouter><HistoryPage /></MemoryRouter>);
    expect(await screen.findByText(/done/)).toBeInTheDocument();
    expect(screen.getByText(/Guilty/)).toBeInTheDocument();
  });

  it("links a running trial to the live view and a finished one to the results page", async () => {
    vi.spyOn(client, "listTrials").mockResolvedValue([
      {
        id: "running-1", created_at: "t", status: "running",
        source_text_preview: "s", target_text_preview: "t", verdict: null, error_message: null,
      },
      {
        id: "done-1", created_at: "t", status: "done",
        source_text_preview: "s", target_text_preview: "t", verdict: "Guilty", error_message: null,
      },
    ]);
    render(<MemoryRouter><HistoryPage /></MemoryRouter>);
    await screen.findByText(/running/);
    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "/trial/running-1");
    expect(links[1]).toHaveAttribute("href", "/trial/done-1/result");
  });
});
