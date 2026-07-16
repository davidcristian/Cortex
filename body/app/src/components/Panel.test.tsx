import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { INITIAL_LINK } from "../overlay/linkState";
import type { Message, OverlayState } from "../overlay/overlayState";
import { Panel } from "./Panel";

const state = (over: Partial<OverlayState> = {}): OverlayState => ({
  mode: "panel",
  sessionId: "s1",
  title: "My chat",
  messages: [],
  sessions: [],
  switcherOpen: false,
  sheetOpen: false,
  pendingConfirm: null,
  reminders: [],
  link: INITIAL_LINK,
  seq: 0,
  touched: false,
  ...over,
});

const userMsg: Message = {
  id: "m0",
  role: "user",
  content: "hi there",
  streaming: false,
  tool: null,
  status: null,
  statusState: null,
  error: null,
};

const reply = (id: string): Message => ({
  id,
  role: "assistant",
  content: `reply ${id}`,
  streaming: false,
  tool: null,
  status: null,
  statusState: null,
  error: null,
});

interface Handlers {
  onToggleTheme?: () => void;
  onSubmit?: (text: string) => void;
  onDismiss?: () => void;
  onNewChat?: () => void;
  onToggleSwitcher?: () => void;
  onToggleSheet?: () => void;
  onSelectSession?: (sessionId: string) => void;
  onRespondConfirm?: (confirmId: string, approved: boolean) => void;
  onDismissReminder?: (reminderId: string) => void;
}

function panelProps(over: Partial<OverlayState>, open: boolean, dark: boolean, handlers: Handlers = {}) {
  return {
    state: state(over),
    open,
    dark,
    onToggleTheme: handlers.onToggleTheme ?? vi.fn(),
    onSubmit: handlers.onSubmit ?? vi.fn(),
    onStop: vi.fn(),
    onDismiss: handlers.onDismiss ?? vi.fn(),
    onNewChat: handlers.onNewChat ?? vi.fn(),
    onToggleSwitcher: handlers.onToggleSwitcher ?? vi.fn(),
    onToggleSheet: handlers.onToggleSheet ?? vi.fn(),
    onSelectSession: handlers.onSelectSession ?? vi.fn(),
    onRespondConfirm: handlers.onRespondConfirm ?? vi.fn(),
    onDismissReminder: handlers.onDismissReminder ?? vi.fn(),
  };
}

function renderPanel(over: Partial<OverlayState>, open: boolean, dark: boolean, handlers: Handlers = {}) {
  return render(<Panel {...panelProps(over, open, dark, handlers)} />);
}

describe("Panel", () => {
  it("shows the title, the sun-form theme icon in light mode, and wires the header buttons", () => {
    const onDismiss = vi.fn();
    const onNewChat = vi.fn();
    const onToggleTheme = vi.fn();
    const onToggleSwitcher = vi.fn();
    renderPanel({}, true, false, { onToggleTheme, onDismiss, onNewChat, onToggleSwitcher });
    expect(screen.getByText("My chat")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Cortex" }).className).toContain("open");
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

  it("leads the header with the connection indicator, reading the state it was given", () => {
    renderPanel(
      { link: { state: "degraded", detail: "store down", probing: false } },
      true,
      false,
    );
    const dot = screen.getByRole("status");
    expect(dot.className).toBe("linkdot warn");
    expect(dot).toHaveAccessibleName("The brain is not serving: store down");
    // It leads the row: the title reads as the brain's, not the other way round.
    expect(dot.nextElementSibling?.textContent).toBe("My chat");
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

  it("renders the approval card in the history while a confirm is pending and wires the answer", () => {
    const onRespondConfirm = vi.fn();
    renderPanel(
      {
        messages: [userMsg],
        pendingConfirm: {
          confirmId: "c-1",
          toolName: "send_email",
          argumentsJson: '{"to":"ada@example.com"}',
          reason: "outbound",
        },
      },
      true,
      false,
      { onRespondConfirm },
    );
    expect(screen.getByRole("group", { name: "Approval required" })).toBeInTheDocument();
    fireEvent.click(screen.getByText("Approve"));
    expect(onRespondConfirm).toHaveBeenCalledWith("c-1", true);
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

  it("shows the reminder stack only when something is due, above the scrolling history", () => {
    const onDismissReminder = vi.fn();
    const onSelectSession = vi.fn();
    const { container, rerender } = render(<Panel {...panelProps({}, true, false)} />);
    expect(screen.queryByLabelText("Due reminders")).toBeNull();

    const props = panelProps(
      {
        reminders: [
          {
            reminderId: "r-1",
            text: "Stretch",
            firedAtUnixMs: 1000,
            recurring: false,
            tainted: false,
            sessionId: "c9",
          },
        ],
      },
      true,
      false,
      { onDismissReminder, onSelectSession },
    );
    rerender(<Panel {...props} />);
    const stack = screen.getByLabelText("Due reminders");
    // Delivery is not conversation: the stack sits outside the log so it cannot scroll away.
    expect(container.querySelector(".history")?.contains(stack)).toBe(false);
    fireEvent.click(screen.getByLabelText("Dismiss reminder"));
    expect(onDismissReminder).toHaveBeenCalledWith("r-1");
    // A reminder's origin opens through the switcher's own handler: same chat load, one path.
    fireEvent.click(screen.getByText("open chat"));
    expect(onSelectSession).toHaveBeenCalledWith("c9");
  });

  it("greets an empty chat with the mark and tappable example prompts that submit", () => {
    const onSubmit = vi.fn();
    const { container } = renderPanel({}, true, false, { onSubmit });
    expect(screen.getByText("Ask me anything")).toBeInTheDocument();
    expect(container.querySelector(".empty .rings")).not.toBeNull();
    fireEvent.click(screen.getByText("Summarize my unread email"));
    expect(onSubmit).toHaveBeenCalledWith("Summarize my unread email");
  });

  it("clears the empty state once the chat has messages", () => {
    renderPanel({ messages: [userMsg] }, true, false);
    expect(screen.queryByText("Ask me anything")).toBeNull();
  });

  it("auto-scrolls the history to the newest message unless the reader scrolled up", () => {
    const props = (messages: Message[]) => panelProps({ messages }, true, false);
    const view = render(<Panel {...props([userMsg])} />);
    const el = view.container.querySelector(".history") as HTMLDivElement;
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: 500 });
    Object.defineProperty(el, "clientHeight", { configurable: true, value: 100 });
    // Pinned at the bottom (the mount default): a new message keeps the tail in view.
    view.rerender(<Panel {...props([userMsg, reply("m1")])} />);
    expect(el.scrollTop).toBe(500);
    // The reader scrolls up to read; the next message must not yank them back down.
    el.scrollTop = 100;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props([userMsg, reply("m1"), reply("m2")])} />);
    expect(el.scrollTop).toBe(100);
    // Returning to (near) the bottom re-pins the tail.
    el.scrollTop = 470;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props([userMsg, reply("m1"), reply("m2"), reply("m3")])} />);
    expect(el.scrollTop).toBe(500);
  });

  it("opens the shortcut sheet from the hint strip's ? and closes it on a sheet click", () => {
    const onToggleSheet = vi.fn();
    renderPanel({}, true, false, { onToggleSheet });
    expect(screen.queryByRole("dialog", { name: "Keyboard shortcuts" })).toBeNull();
    fireEvent.click(screen.getByLabelText("Shortcuts"));
    expect(onToggleSheet).toHaveBeenCalledOnce();
    renderPanel({ sheetOpen: true }, true, false, { onToggleSheet });
    fireEvent.click(screen.getByRole("dialog", { name: "Keyboard shortcuts" }));
    expect(onToggleSheet).toHaveBeenCalledTimes(2);
  });
});
