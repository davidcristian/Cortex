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
  it("shows the title, the sun-form theme icon in light mode, and wires the header buttons", () => {
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
    const icon = screen.getByLabelText("Toggle theme").querySelector("svg.sunmoon");
    expect(icon).not.toBeNull();
    expect(icon?.classList.contains("dark")).toBe(false);
    fireEvent.click(screen.getByLabelText("Toggle theme"));
    fireEvent.click(screen.getByLabelText("New chat"));
    fireEvent.click(screen.getByLabelText("Dismiss"));
    expect(onToggleTheme).toHaveBeenCalledOnce();
    expect(onNewChat).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("marks the theme icon dark, is not open when closed, and renders its messages", () => {
    render(
      <Panel
        state={state({ messages: [userMsg], mode: "hidden" })}
        open={false}
        dark={true}
        onToggleTheme={vi.fn()}
        onSubmit={vi.fn()}
        onDismiss={vi.fn()}
        onNewChat={vi.fn()}
      />,
    );
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog.className).not.toContain("open");
    expect(dialog.className).not.toContain("to-orb");
    const icon = screen.getByLabelText("Toggle theme").querySelector("svg.sunmoon");
    expect(icon?.classList.contains("dark")).toBe(true);
    expect(screen.getByText(/hi/u)).toBeInTheDocument();
  });

  it("parks the closed panel at the corner while the orb owns the turn", () => {
    render(
      <Panel
        state={state({ mode: "orb" })}
        open={false}
        dark={false}
        onToggleTheme={vi.fn()}
        onSubmit={vi.fn()}
        onDismiss={vi.fn()}
        onNewChat={vi.fn()}
      />,
    );
    expect(screen.getByRole("dialog", { hidden: true }).className).toContain("to-orb");
  });
});
