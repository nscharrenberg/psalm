import { MantineProvider, Button } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("Mantine test environment", () => {
  it("renders a Mantine component without crashing", () => {
    render(
      <MantineProvider>
        <Button>Test</Button>
      </MantineProvider>,
    );
    expect(screen.getByRole("button", { name: "Test" })).toBeInTheDocument();
  });
});
