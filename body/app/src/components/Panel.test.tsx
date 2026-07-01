import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Message, OverlayState } from "../overlay/overlayState";
import { Panel } from "./Panel";

const state = (over: Partial<OverlayState> = {}): OverlayState => ({
  mode: "panel",
  title: "My chat",
  messages: [],
  seq: 0,
  ...over,
});

const userMsg: Message = {
  id: "m0",
  role: "user",
  content: "hi there",
  streaming: false,
  tool: null,
  status: null,
  error: null,
};

describe("Panel", () => {
  it("shows the title, the sun glyph in light mode, and wires the header buttons", () => {
    const onDismiss = vi.fn();
    const onNewChat = vi.fn();
    const onToggleTheme = vi.fn();
    render(
      <Panel
        state={state()}
        open={true}
        dark={false}
        onToggleTheme={onToggleTheme}
        onSubmit={vi.fn()}
        onDismiss={onDismiss}
        onNewChat={onNewChat}
      />,
    );
    expect(screen.getByText("My chat")).toBeInTheDocument();
    expect(screen.getByRole("dialog").className).toContain("open");
    expect(screen.getByLabelText("Toggle theme").textContent).toBe("☀");
    fireEvent.click(screen.getByLabelText("Toggle theme"));
    fireEvent.click(screen.getByLabelText("New chat"));
    fireEvent.click(screen.getByLabelText("Dismiss"));
    expect(onToggleTheme).toHaveBeenCalledOnce();
    expect(onNewChat).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("shows the moon glyph in dark mode, is not open when closed, and renders its messages", () => {
    render(
      <Panel
        state={state({ messages: [userMsg] })}
        open={false}
        dark={true}
        onToggleTheme={vi.fn()}
        onSubmit={vi.fn()}
        onDismiss={vi.fn()}
        onNewChat={vi.fn()}
      />,
    );
    expect(screen.getByRole("dialog", { hidden: true }).className).not.toContain("open");
    expect(screen.getByLabelText("Toggle theme").textContent).toBe("☾");
    expect(screen.getByText(/hi/u)).toBeInTheDocument();
  });
});
