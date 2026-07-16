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
        onRename={vi.fn()}
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
    render(<SessionList sessions={[]} currentId="c1" onSelect={vi.fn()} onRename={vi.fn()} />);
    expect(screen.getByText(/no other chats/iu)).toBeInTheDocument();
  });

  it("opens an inline editor on the pencil, prefilled, and saves the trimmed name", () => {
    const onRename = vi.fn();
    render(
      <SessionList
        sessions={[summary(), summary({ sessionId: "c2", title: "Second" })]}
        currentId="c1"
        onSelect={vi.fn()}
        onRename={onRename}
      />,
    );
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    const input = screen.getByLabelText<HTMLInputElement>("New chat name");
    expect(input.value).toBe("First chat"); // prefilled with the current title
    // The other row stays a normal, selectable item while one is being renamed.
    expect(screen.getByText("Second")).toBeInTheDocument();
    fireEvent.change(input, { target: { value: "  Everything about cats  " } });
    fireEvent.submit(input);
    expect(onRename).toHaveBeenCalledWith("c1", "Everything about cats"); // trimmed
    // The editor closes on save, so the row is a normal item again.
    expect(screen.queryByLabelText("New chat name")).not.toBeInTheDocument();
  });

  it("submits an empty label to clear a custom title back to the derived one", () => {
    const onRename = vi.fn();
    render(
      <SessionList sessions={[summary()]} currentId="c1" onSelect={vi.fn()} onRename={onRename} />,
    );
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    fireEvent.change(screen.getByLabelText("New chat name"), { target: { value: "   " } });
    fireEvent.click(screen.getByLabelText("Save name"));
    expect(onRename).toHaveBeenCalledWith("c1", ""); // "" is the clear-the-override signal
  });

  it("cancels on Escape without renaming, and ignores other keys", () => {
    const onRename = vi.fn();
    render(
      <SessionList sessions={[summary()]} currentId="c1" onSelect={vi.fn()} onRename={onRename} />,
    );
    fireEvent.click(screen.getByLabelText("Rename First chat"));
    const input = screen.getByLabelText<HTMLInputElement>("New chat name");
    fireEvent.keyDown(input, { key: "a" }); // a non-Escape key leaves the editor open
    expect(screen.getByLabelText("New chat name")).toBeInTheDocument();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByLabelText("New chat name")).not.toBeInTheDocument();
    expect(onRename).not.toHaveBeenCalled();
  });
});
