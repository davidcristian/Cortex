import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SessionSummary } from "../bridge/types";
import { SessionList } from "./SessionList";

const summary = (over: Partial<SessionSummary> = {}): SessionSummary => ({
  sessionId: "c1",
  title: "First chat",
  preview: "hello there",
  lastActivityUnixMs: Date.now() - 5 * 60_000,
  ...over,
});

describe("SessionList", () => {
  it("renders each chat's title and preview, marks the current, and selects on click", () => {
    const onSelect = vi.fn();
    render(
      <SessionList
        sessions={[summary(), summary({ sessionId: "c2", title: "Second", preview: "world" })]}
        currentId="c2"
        onSelect={onSelect}
      />,
    );
    expect(screen.getByText("First chat")).toBeInTheDocument();
    expect(screen.getByText("world")).toBeInTheDocument();
    // The current chat's button carries the `current` marker class.
    const current = screen.getByText("Second").closest("button");
    expect(current?.className).toContain("current");
    fireEvent.click(screen.getByText("First chat"));
    expect(onSelect).toHaveBeenCalledWith("c1");
  });

  it("shows an empty-state line when there are no chats", () => {
    render(<SessionList sessions={[]} currentId="c1" onSelect={vi.fn()} />);
    expect(screen.getByText(/no other chats/iu)).toBeInTheDocument();
  });
});
