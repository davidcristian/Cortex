import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WOBBLE } from "../mark/marks";
import { INITIAL_LINK } from "../overlay/linkState";
import type { ConsoleTab, Message, OverlayState } from "../overlay/overlayState";
import { Panel } from "./Panel";

const state = (over: Partial<OverlayState> = {}): OverlayState => ({
  mode: "panel",
  sessionId: "s1",
  title: "My chat",
  messages: [],
  sessions: [],
  switcherOpen: false,
  consoleTab: null,
  pendingConfirm: null,
  reminders: [],
  link: INITIAL_LINK,
  capturing: false,
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
  thoughts: "",
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
  thoughts: "",
  error: null,
});

interface Handlers {
  onPickMark?: (name: string) => void;
  onPickTheme?: (name: string | null) => void;
  onToggleConsole?: (tab: ConsoleTab) => void;
  onOpenConsole?: (tab: ConsoleTab) => void;
  onCloseConsole?: () => void;
  onToggleTheme?: () => void;
  onSubmit?: (text: string) => void;
  onDismiss?: () => void;
  onNewChat?: () => void;
  onToggleSwitcher?: () => void;
  onSelectSession?: (sessionId: string) => void;
  onRenameSession?: (sessionId: string, title: string) => void;
  onDeleteSession?: (sessionId: string) => void;
  onPinSession?: (sessionId: string, pinned: boolean) => void;
  onRespondConfirm?: (confirmId: string, approved: boolean) => void;
  onDismissReminder?: (reminderId: string) => void;
}

function panelProps(over: Partial<OverlayState>, open: boolean, dark: boolean, handlers: Handlers = {}) {
  return {
    state: state(over),
    open,
    dark,
    mark: WOBBLE,
    themeName: null,
    onPickTheme: handlers.onPickTheme ?? vi.fn(),
    onPickMark: handlers.onPickMark ?? vi.fn(),
    onToggleConsole: handlers.onToggleConsole ?? vi.fn(),
    onOpenConsole: handlers.onOpenConsole ?? vi.fn(),
    onCloseConsole: handlers.onCloseConsole ?? vi.fn(),
    onToggleTheme: handlers.onToggleTheme ?? vi.fn(),
    onSubmit: handlers.onSubmit ?? vi.fn(),
    onStop: vi.fn(),
    onDismiss: handlers.onDismiss ?? vi.fn(),
    onNewChat: handlers.onNewChat ?? vi.fn(),
    onToggleSwitcher: handlers.onToggleSwitcher ?? vi.fn(),
    onSelectSession: handlers.onSelectSession ?? vi.fn(),
    onRenameSession: handlers.onRenameSession ?? vi.fn(),
    onDeleteSession: handlers.onDeleteSession ?? vi.fn(),
    onPinSession: handlers.onPinSession ?? vi.fn(),
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

  it("ends the header with the connection indicator, reading the state it was given", () => {
    renderPanel(
      { link: { state: "degraded", detail: "store down", probing: false } },
      true,
      false,
    );
    const dot = screen.getByRole("status");
    expect(dot.className).toBe("linkdot warn");
    expect(dot).toHaveAccessibleName("The brain is not serving: store down");
    // It closes the row instead of leading it: the title starts the header (and owns the panel's
    // rounded corner), and the dot opens the button cluster as the state half of the same group.
    expect(dot.previousElementSibling?.textContent).toBe("My chat");
    expect(dot.nextElementSibling).toBe(screen.getByLabelText("Recent chats"));
  });

  it("appears with the capture ring against the title, so nothing on the row moves", () => {
    renderPanel({ capturing: true }, true, false);
    const [capture, link] = screen.getAllByRole("status");
    expect(capture?.className).toBe("capturedot");
    expect(link?.className).toContain("linkdot");
    expect(capture).toHaveAccessibleName(
      "The assistant asked to look at your screen during this reply",
    );
    // The two are one row of state and move together. Split, the ring would be the one thing left
    // beside the title, appearing and vanishing with every capture the assistant asks for.
    //
    // The order within the pair is load-bearing, not cosmetic. The title is the row's only flexible
    // item, so it pays for anything inserted directly against it and nothing else moves. Put the
    // ring on the far side of the dot and the dot plus every button slide left by the ring's width
    // the instant a capture starts, which is a header that twitches mid-turn.
    expect(capture?.previousElementSibling?.textContent).toBe("My chat");
    expect(capture?.nextElementSibling).toBe(link);
    expect(link?.nextElementSibling).toBe(screen.getByLabelText("Recent chats"));
  });

  it("marks the theme icon dark, is not open when closed, and renders its messages", () => {
    const { container } = renderPanel({ messages: [userMsg], mode: "hidden" }, false, true);
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog.className).not.toContain("open");
    expect(dialog.className).not.toContain("to-orb");
    const icon = screen.getByLabelText("Toggle theme").querySelector("svg.sunmoon");
    expect(icon?.classList.contains("dark")).toBe(true);
    // Read off the bubble rather than searched for: a reply is rendered one span per word, so it
    // matches no single text node, and a loose pattern now finds the "Shift" keycap instead.
    expect(container.querySelector(".b-user")?.textContent).toContain("hi there");
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
          { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000, pinned: false },
        ],
      },
      true,
      false,
      { onSelectSession },
    );
    fireEvent.click(screen.getByText("First chat"));
    expect(onSelectSession).toHaveBeenCalledWith("c1");
  });

  it("threads the delete handler to the switcher: confirming a row's trash deletes it", () => {
    const onDeleteSession = vi.fn();
    renderPanel(
      {
        switcherOpen: true,
        sessions: [
          { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000, pinned: false },
        ],
      },
      true,
      false,
      { onDeleteSession },
    );
    fireEvent.click(screen.getByLabelText("Delete First chat"));
    fireEvent.click(screen.getByLabelText("Confirm delete First chat"));
    expect(onDeleteSession).toHaveBeenCalledWith("c1");
  });

  it("threads the pin handler to the switcher: clicking a row's pin toggles it", () => {
    const onPinSession = vi.fn();
    renderPanel(
      {
        switcherOpen: true,
        sessions: [
          { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000, pinned: false },
        ],
      },
      true,
      false,
      { onPinSession },
    );
    fireEvent.click(screen.getByLabelText("Pin First chat"));
    expect(onPinSession).toHaveBeenCalledWith("c1", true);
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

  it("opens the console on the tab each door names: the sliders and the mark on appearance", () => {
    const onToggleConsole = vi.fn();
    renderPanel({}, true, false, { onToggleConsole });
    fireEvent.click(screen.getByLabelText("Settings"));
    expect(onToggleConsole).toHaveBeenCalledWith("appearance");
    // The mark is the shortcut: it is the thing the appearance tab's mark row changes, so it says
    // what it shows and where it lands. Named for the tab, not for the settings sheet that used to
    // be there: the view is gone, and a stale label is the part of a rename only a reader hears.
    fireEvent.click(screen.getByLabelText("Mark: Wobble. Open appearance"));
    expect(onToggleConsole).toHaveBeenCalledTimes(2);
    expect(onToggleConsole).toHaveBeenLastCalledWith("appearance");
  });

  it("becomes the console's appearance tab when it is open, wiring its choices and the way back", () => {
    const onPickMark = vi.fn();
    const onPickTheme = vi.fn();
    const onCloseConsole = vi.fn();
    const { container } = renderPanel({ consoleTab: "appearance" }, true, false, {
      onPickMark,
      onPickTheme,
      onCloseConsole,
    });
    expect(screen.getByRole("region", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("tabpanel", { name: "Appearance" })).toBeInTheDocument();
    // The chat is still mounted (a half-typed draft survives the trip) but out of the flow, so
    // the panel is only as tall as the tiles.
    expect(container.querySelector(".view.gone")).not.toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Foam" }));
    expect(onPickMark).toHaveBeenCalledWith("foam");
    fireEvent.click(screen.getByRole("radio", { name: "daylight" }));
    expect(onPickTheme).toHaveBeenCalledWith("daylight");
    fireEvent.click(screen.getByLabelText("Back to chat"));
    expect(onCloseConsole).toHaveBeenCalledOnce();
  });

  it("routes each console tab to its own view, so the strip switches by morphing the panel", () => {
    const onOpenConsole = vi.fn();
    const props = (tab: ConsoleTab) =>
      panelProps({ consoleTab: tab }, true, false, { onOpenConsole });
    const view = render(<Panel {...props("appearance")} />);
    fireEvent.click(screen.getByRole("tab", { name: "Shortcuts" }));
    expect(onOpenConsole).toHaveBeenCalledWith("shortcuts");

    // The switch is a VIEW change, not a swap inside one: the tab being left is held out of the
    // layout flow for one morph and fades over the one arriving, exactly as a whole view does.
    view.rerender(<Panel {...props("shortcuts")} />);
    expect(view.container.querySelector(".view.out")?.textContent).toContain("Theme");
    expect(screen.getByRole("tabpanel", { name: "Shortcuts" })).toBeInTheDocument();
    // Both panes cross with `swap`, which trades the rise-and-sink for a plain fade: the header
    // and the tab strip are the same chrome in both, so moving them would read as the strip
    // jittering rather than as the content changing under a strip that stays put.
    expect(view.container.querySelector(".view.out")?.className).toContain("swap");
    expect(view.container.querySelector(".views > div:not(.out):not(.gone)")?.className).toContain(
      "swap",
    );
  });

  it("exposes one console to assistive tech while two tabs are crossing, and names the leaver", () => {
    const props = (tab: ConsoleTab | null) => panelProps({ consoleTab: tab }, true, false);
    const view = render(<Panel {...props("appearance")} />);
    view.rerender(<Panel {...props("shortcuts")} />);
    // Two panes are mounted, both a region called "Settings" holding a tab list and a tab panel.
    // Only the arriving one is exposed: `getByRole` fails on a second, and the pane on its way
    // out is the one hidden, so a reader is never handed the tab that was just left.
    expect(view.container.querySelectorAll(".pane")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getAllByRole("tablist")).toHaveLength(1);
    expect(screen.getByRole("tabpanel", { name: "Shortcuts" })).toBeInTheDocument();
    expect(view.container.querySelector(".view.out")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("hands focus to the console and takes it back into the composer on the way out", () => {
    const props = (tab: ConsoleTab | null) => panelProps({ consoleTab: tab }, true, false);
    const view = render(<Panel {...props(null)} />);
    const field = screen.getByLabelText("Message");
    expect(document.activeElement).toBe(field);
    // Into the console: the pane that arrives takes focus, because the chat pane it came from is
    // one morph away from display:none, which would drop focus to the body.
    view.rerender(<Panel {...props("appearance")} />);
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Appearance" }));
    // And back out: the chat is the active view again, so the caret returns to the draft rather
    // than staying on a tab strip that is fading out.
    view.rerender(<Panel {...props(null)} />);
    expect(document.activeElement).toBe(field);
  });

  it("keeps the rise-and-sink for the chat leaving, which shares no chrome with the console", () => {
    const props = (tab: ConsoleTab | null) => panelProps({ consoleTab: tab }, true, false);
    const view = render(<Panel {...props(null)} />);
    view.rerender(<Panel {...props("appearance")} />);
    // Nothing in the chat is in the same place as anything in the console, so this crossing is
    // the full one: the console rises into the space the panel is opening, the chat sinks out.
    expect(view.container.querySelector(".view.out")?.className).toBe("view out");
    expect(view.container.querySelector(".views > div:not(.out):not(.gone)")?.className).toBe(
      "view",
    );
  });

  it("holds the view it is leaving on screen for one morph, out of the flow", () => {
    const props = (over: Partial<OverlayState>) => panelProps(over, true, false);
    const view = render(<Panel {...props({ consoleTab: "shortcuts" })} />);
    expect(view.container.querySelector(".view.out")).toBeNull();
    // Back to the chat: the shortcut list stays, lifted out of flow so it cannot define the
    // height the panel is easing to, and fades out over the chat arriving underneath it.
    view.rerender(<Panel {...props({})} />);
    const leaving = view.container.querySelector(".view.out");
    expect(leaving?.textContent).toContain("Switcher");
    expect(screen.getByLabelText("Recent chats")).toBeInTheDocument();
  });

  it("greets an empty chat with the mark and tappable example prompts that submit", () => {
    const onSubmit = vi.fn();
    const { container } = renderPanel({}, true, false, { onSubmit });
    expect(screen.getByText("Ask me anything")).toBeInTheDocument();
    expect(container.querySelector(".empty .markbtn .mark")).not.toBeNull();
    fireEvent.click(screen.getByText("Summarize my unread email"));
    expect(onSubmit).toHaveBeenCalledWith("Summarize my unread email");
  });

  it("clears the empty state once the chat has messages", () => {
    renderPanel({ messages: [userMsg] }, true, false);
    expect(screen.queryByText("Ask me anything")).toBeNull();
  });

  it("keeps the invitation and the bubbles that replace it in the same floored column", () => {
    // The panel must not shrink when the first message is sent, and what stops it is a min-height
    // on `.log` sized to the empty state (overlay.css). That only holds while BOTH the empty state
    // and the messages that replace it are inside that one column, which is a structural contract
    // no stylesheet can defend: pulling either back out to `.history` would silently hand the
    // user back a panel that shrinks the moment they use it.
    const empty = renderPanel({}, true, false).container;
    expect(empty.querySelector(".history > .log > .empty")).not.toBeNull();
    cleanup();
    const talking = renderPanel({ messages: [userMsg] }, true, false).container;
    expect(talking.querySelector(".history > .log > .bubble")).not.toBeNull();
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

  it("holds the tail when a growing draft eats the log's height, unless the reader scrolled up", () => {
    // The composer and the log are flex siblings and the log is the one that yields, so a draft
    // that restacks the pill takes that height straight out of the visible window (52px measured
    // in Chromium, 122px at the field's ceiling) while the engine leaves `scrollTop` alone. Without
    // this the newest reply slides out from under the reader while they answer it.
    const view = render(<Panel {...panelProps({ messages: [userMsg, reply("m1")] }, true, false)} />);
    const el = view.container.querySelector(".history") as HTMLDivElement;
    const field = screen.getByLabelText("Message") as HTMLTextAreaElement;
    const pill = field.parentElement as HTMLDivElement;
    Object.defineProperty(field, "clientHeight", { configurable: true, value: 34 });
    Object.defineProperty(field, "scrollHeight", { configurable: true, get: () => 50 });
    Object.defineProperty(pill, "offsetHeight", { configurable: true, get: () => 90 });
    // The log's own numbers: the tail is at 500, and the draft is about to take the window with it.
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: 500 });
    Object.defineProperty(el, "clientHeight", { configurable: true, value: 100 });
    fireEvent.change(field, { target: { value: "a draft\nover two lines" } });
    expect(el.scrollTop).toBe(500);
    // A reader who has scrolled up keeps their place: growing the pill is not a reason to yank them
    // back down, exactly as a new message is not.
    el.scrollTop = 100;
    fireEvent.scroll(el);
    Object.defineProperty(pill, "offsetHeight", { configurable: true, get: () => 130 });
    fireEvent.change(field, { target: { value: "a draft\nover two lines\nand a third" } });
    expect(el.scrollTop).toBe(100);
  });

  it("opens the console's shortcuts tab from the hint strip's ? and comes back from it", () => {
    const onToggleConsole = vi.fn();
    const onCloseConsole = vi.fn();
    renderPanel({}, true, false, { onToggleConsole, onCloseConsole });
    expect(screen.queryByRole("region", { name: "Settings" })).toBeNull();
    fireEvent.click(screen.getByLabelText("Shortcuts"));
    expect(onToggleConsole).toHaveBeenCalledWith("shortcuts");
    cleanup();
    renderPanel({ consoleTab: "shortcuts" }, true, false, { onToggleConsole, onCloseConsole });
    expect(screen.getByRole("tabpanel", { name: "Shortcuts" })).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Back to chat"));
    expect(onCloseConsole).toHaveBeenCalledOnce();
  });

  it("gives every hint-strip key its own cap, the way the shortcut list does", () => {
    renderPanel({}, true, false);
    const hint = (text: string) =>
      [...document.querySelectorAll(".hints span")].find((s) => s.textContent?.includes(text));
    // A chord is drawn as the keys it is: the newline hint is Shift AND Return, two caps, which is
    // how the console's list reads it too. Shift is spelled out like Ctrl and Alt, so the drawn cap
    // left is return, the one key here with no name worth writing.
    expect(hint("newline")?.querySelectorAll("b")).toHaveLength(2);
    expect(hint("newline")?.querySelector("b")?.textContent).toBe("Shift");
    expect(hint("newline")?.querySelectorAll("b.key")).toHaveLength(1);
    for (const cap of hint("newline")?.querySelectorAll("b.key") ?? []) {
      expect(cap.querySelectorAll("svg")).toHaveLength(1);
    }
    expect(hint("send")?.querySelectorAll("b.key")).toHaveLength(1);
    // Matched on "N new" rather than "new", which "newline" would answer to first.
    expect([...(hint("N new")?.querySelectorAll("b") ?? [])].map((b) => b.textContent)).toEqual([
      "Ctrl",
      "N",
    ]);
  });
});
