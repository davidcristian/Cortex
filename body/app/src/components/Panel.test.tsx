import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Message, OverlayState } from "../overlay/overlayState";
import { Panel } from "./Panel";

const state = (over: Partial<OverlayState> = {}): OverlayState => ({
  mode: "panel",
  sessionId: "s1",
  title: "My chat",
  messages: [],
  sessions: [],
  switcherOpen: false,
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

interface Handlers {
  onToggleTheme?: () => void;
  onDismiss?: () => void;
  onNewChat?: () => void;
  onToggleSwitcher?: () => void;
  onSelectSession?: (sessionId: string) => void;
}

function renderPanel(over: Partial<OverlayState>, open: boolean, dark: boolean, handlers: Handlers = {}) {
  return render(
    <Panel
      state={state(over)}
      open={open}
      dark={dark}
      onToggleTheme={handlers.onToggleTheme ?? vi.fn()}
      onSubmit={vi.fn()}
      onStop={vi.fn()}
      onDismiss={handlers.onDismiss ?? vi.fn()}
      onNewChat={handlers.onNewChat ?? vi.fn()}
      onToggleSwitcher={handlers.onToggleSwitcher ?? vi.fn()}
      onSelectSession={handlers.onSelectSession ?? vi.fn()}
    />,
  );
}

describe("Panel", () => {
  it("shows the title, the sun-form theme icon in light mode, and wires the header buttons", () => {
    const onDismiss = vi.fn();
    const onNewChat = vi.fn();
    const onToggleTheme = vi.fn();
    const onToggleSwitcher = vi.fn();
    renderPanel({}, true, false, { onToggleTheme, onDismiss, onNewChat, onToggleSwitcher });
    expect(screen.getByText("My chat")).toBeInTheDocument();
    expect(screen.getByRole("dialog").className).toContain("open");
    const icon = screen.getByLabelText("Toggle theme").querySelector("svg.sunmoon");
    expect(icon).not.toBeNull();
    expect(icon?.classList.contains("dark")).toBe(false);
    fireEvent.click(screen.getByLabelText("Toggle theme"));
    fireEvent.click(screen.getByLabelText("New chat"));
    fireEvent.click(screen.getByLabelText("Dismiss"));
    fireEvent.click(screen.getByLabelText("Recent chats"));
    expect(onToggleTheme).toHaveBeenCalledOnce();
    expect(onNewChat).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onToggleSwitcher).toHaveBeenCalledOnce();
  });

  it("marks the theme icon dark, is not open when closed, and renders its messages", () => {
    renderPanel({ messages: [userMsg], mode: "hidden" }, false, true);
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog.className).not.toContain("open");
    expect(dialog.className).not.toContain("to-orb");
    const icon = screen.getByLabelText("Toggle theme").querySelector("svg.sunmoon");
    expect(icon?.classList.contains("dark")).toBe(true);
    expect(screen.getByText(/hi/u)).toBeInTheDocument();
  });

  it("parks the closed panel at the corner while the orb owns the turn", () => {
    renderPanel({ mode: "orb" }, false, false);
    expect(screen.getByRole("dialog", { hidden: true }).className).toContain("to-orb");
  });

  it("shows the switcher list when open and selecting a chat calls back", () => {
    const onSelectSession = vi.fn();
    renderPanel(
      {
        switcherOpen: true,
        sessions: [
          { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000 },
        ],
      },
      true,
      false,
      { onSelectSession },
    );
    fireEvent.click(screen.getByText("First chat"));
    expect(onSelectSession).toHaveBeenCalledWith("c1");
  });
});
