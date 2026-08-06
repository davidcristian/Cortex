import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LUCID, STILL } from "../edge/edges";
import { MULL } from "../mark/marks";
import { INITIAL_LINK } from "../overlay/linkState";
import type { ConsoleTab, Message, OverlayState } from "../overlay/overlayState";
import { laysEverything, stubRoll } from "../test-setup";
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
  notice: null,
  arrival: 0,
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
    mark: MULL,
    edge: STILL,
    themeName: null,
    onPickTheme: handlers.onPickTheme ?? vi.fn(),
    onPickMark: handlers.onPickMark ?? vi.fn(),
    onPickEdge: vi.fn(),
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

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

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
    // And it loads SILENTLY: the row's own accessible name is the title, so a live region
    // repeating it would read the reader the label they just pressed (`overlay/notice.ts`).
    expect(onSelectSession).toHaveBeenCalledWith("c1", false);
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

  it("shows the reminder stack only when something is due, above the scrolling history", async () => {
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
    // A reminder's origin opens through the switcher's own handler: same chat load, one path.
    // Read before the dismissal, which takes the card away with it. The two doors part on the
    // second argument only: this control is named "open chat" and not for the chat, so the chat
    // that arrives is announced where a switcher row's is not (`overlay/notice.ts`).
    fireEvent.click(screen.getByText("open chat"));
    expect(onSelectSession).toHaveBeenCalledWith("c9", true);
    // The ack goes up in the frame the check is pressed; the row it removes is held on screen for
    // the length of its own roll by the stack itself (`overlay/usePresence.ts`).
    fireEvent.click(screen.getByLabelText("Dismiss reminder"));
    expect(onDismissReminder).toHaveBeenCalledWith("r-1");
  });

  it("opens the console on the tab each door names: the sliders and the mark on appearance", () => {
    const onToggleConsole = vi.fn();
    renderPanel({}, true, false, { onToggleConsole });
    fireEvent.click(screen.getByLabelText("Settings"));
    expect(onToggleConsole).toHaveBeenCalledWith("appearance");
    // The mark is the shortcut: it is the thing the appearance tab's mark row changes, so it says
    // what it shows and where it lands. Named for the tab, not for the settings sheet that used to
    // be there: the view is gone, and a stale label is the part of a rename only a reader hears.
    fireEvent.click(screen.getByLabelText("Mark: Mull. Open appearance"));
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
    expect(screen.getByRole("tabpanel", { name: "Face" })).toBeInTheDocument();
    // The chat is still mounted (a half-typed draft survives the trip) but out of the flow, so
    // the panel is only as tall as the tiles.
    expect(container.querySelector(".view.gone")).not.toBeNull();
    // Picked by its label, stored under its key, and the two match again: the keys were healed
    // once the maintainer confirmed the project is private, with the shipped names kept as resolver
    // aliases so a pick stored under "foam" still lands on Tangent.
    fireEvent.click(screen.getByRole("radio", { name: "Tangent" }));
    expect(onPickMark).toHaveBeenCalledWith("tangent");
    fireEvent.click(screen.getByRole("radio", { name: "Daylight" }));
    expect(onPickTheme).toHaveBeenCalledWith("daylight");
    fireEvent.click(screen.getByLabelText("Back to chat"));
    expect(onCloseConsole).toHaveBeenCalledOnce();
  });

  it("switches tabs inside one view, so the panel neither resizes nor replays its chrome", () => {
    const onOpenConsole = vi.fn();
    const props = (tab: ConsoleTab) =>
      panelProps({ consoleTab: tab }, true, false, { onOpenConsole });
    const view = render(<Panel {...props("appearance")} />);
    fireEvent.click(screen.getByRole("tab", { name: "Chords" }));
    expect(onOpenConsole).toHaveBeenCalledWith("shortcuts");

    // A tab is not a view. Both are mounted in one pane, stacked, so the taller decides the height
    // and nothing about the panel moves when the tab changes; the header and its back chevron are
    // the same elements before and after, so their enter animation does not run again.
    view.rerender(<Panel {...props("shortcuts")} />);
    expect(view.container.querySelectorAll(".pane")).toHaveLength(1);
    expect(view.container.querySelector(".view.out")).toBeNull();
    expect(view.container.querySelectorAll(".tabpane")).toHaveLength(2);
  });

  it("keeps the inactive tab's box but exposes neither it nor its content", () => {
    const props = (tab: ConsoleTab) => panelProps({ consoleTab: tab }, true, false);
    const view = render(<Panel {...props("shortcuts")} />);
    // The point of mounting both is the box: the panel is as tall as the taller tab either way, so
    // switching cannot resize it. Everything else about the hidden one is taken away, or a reader
    // stepping through the console would meet two equal tab panels and both sets of controls.
    const panes = [...view.container.querySelectorAll(".tabpane")];
    expect(panes.map((p) => p.getAttribute("aria-hidden"))).toEqual(["true", "false"]);
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
    expect(screen.getByRole("tabpanel", { name: "Chords" })).toBeInTheDocument();
  });

  it("hands focus to the console and takes it back into the composer on the way out", () => {
    const props = (tab: ConsoleTab | null) => panelProps({ consoleTab: tab }, true, false);
    const view = render(<Panel {...props(null)} />);
    const field = screen.getByLabelText("Message");
    expect(document.activeElement).toBe(field);
    // Into the console: the pane that arrives takes focus, because the chat pane it came from is
    // one morph away from display:none, which would drop focus to the body.
    view.rerender(<Panel {...props("appearance")} />);
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Face" }));
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

  it("takes the leaving view out of the tab order for as long as it is out of the tree's", () => {
    const props = (over: Partial<OverlayState>) => panelProps(over, true, false);
    const view = render(<Panel {...props({ consoleTab: "shortcuts" })} />);
    const views = () => [...view.container.querySelectorAll(".views > .view")];
    // Settled: the chat is `gone`, which is display:none, and the console is the live view.
    expect(views().map((pane) => pane.hasAttribute("inert"))).toEqual([true, false]);

    // Leaving: the console is still mounted and fading, and for that whole 380ms it was announced
    // as hidden and still reachable by Tab, which is three stops (the chevron and both faces) in a
    // pane the user has already left. Now the two attributes say the same thing.
    view.rerender(<Panel {...props({})} />);
    const leaving = view.container.querySelector(".view.out") as HTMLElement;
    expect(leaving.getAttribute("aria-hidden")).toBe("true");
    expect(leaving.hasAttribute("inert")).toBe(true);
    expect(view.container.querySelector(".views > .view:not(.out)")).not.toHaveAttribute("inert");
  });

  it("takes a dismissed panel out of the tab order, orb and hidden alike", () => {
    // The outermost of the three: the panel is never unmounted, so a dismissed one was opacity 0
    // with everything in it still tabbable, and Tab walked an invisible panel. Measured in
    // Chromium at 900x900 before this: six presses reached the reminder rows' buttons.
    for (const mode of ["hidden", "orb"] as const) {
      const { container, unmount } = renderPanel({ mode }, false, false);
      const panel = container.querySelector(".panel") as HTMLElement;
      expect(panel.getAttribute("aria-hidden")).toBe("true");
      expect(panel.hasAttribute("inert")).toBe(true);
      unmount();
    }
    const open = renderPanel({}, true, false);
    const panel = open.container.querySelector(".panel") as HTMLElement;
    expect(panel.getAttribute("aria-hidden")).toBe("false");
    expect(panel.hasAttribute("inert")).toBe(false);
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

  it("sizes that floor off the invitation it is copying, while the invitation is on screen", () => {
    // The other half of the same contract: the floor is `--chat-floor` and the empty state is what
    // publishes it (overlay/measured.ts), so an edit to the mark, the invitation or the chips moves
    // the floor with it instead of leaving a constant behind to drift.
    const settle = laysEverything(207);
    try {
      renderPanel({}, true, false);
      expect(document.documentElement.style.getPropertyValue("--chat-floor")).toBe("207px");
    } finally {
      document.documentElement.style.removeProperty("--chat-floor");
      settle();
    }
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

  it("holds the log's place while a section rolls open in the chrome beside it", () => {
    // The switcher list and the reminder stack are siblings of the history, so a roll's start event
    // goes up past the log to the panel and the box itself hears nothing. At the panel's ceiling
    // their growth comes out of the log's window all the same: measured at 640x720 on a full
    // history, opening the switcher took the window 293px to 73px with `scrollTop` left where it
    // was, so the end of the reply went from 3px below the fold to 223px. The log listens on the
    // column the panel renders this view into, and this is that wire.
    const land = stubRoll();
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) =>
      frames.push(callback),
    );
    vi.stubGlobal("cancelAnimationFrame", () => undefined);
    // One array across both renders, so opening the switcher is the only thing that changed: a new
    // list of messages is what the tail pin itself answers, and it would scroll this log on its own.
    const messages = [userMsg, reply("m1")];
    const props = (switcherOpen: boolean) => panelProps({ messages, switcherOpen }, true, false);
    const view = render(<Panel {...props(false)} />);
    const el = view.container.querySelector(".history") as HTMLDivElement;
    let seen = 293;
    Object.defineProperty(el, "scrollHeight", { configurable: true, get: () => 704 });
    Object.defineProperty(el, "clientHeight", { configurable: true, get: () => seen });
    el.scrollTop = 408;
    view.rerender(<Panel {...props(true)} />);
    // Frame zero of the roll, where the log is still the size it was: the ride reads the reader's
    // distance from the end there (3px, so they are at it) and moves nothing yet.
    frames[frames.length - 1]?.(0);
    expect(el.scrollTop).toBe(408);
    // And now the roll takes the window, the panel having nothing left to give.
    seen = 73;
    frames[frames.length - 1]?.(0);
    expect(el.scrollTop).toBe(628);
    land();
  });

  it("hands the log back its place after a trip to the console, ignoring the layout's scrolling", () => {
    // The trip takes the scroll position twice over: the view being left is lifted out of the flow
    // (`.view.out`), which hands the history its whole content as its window so there is nothing
    // left to scroll, and a morph later `.view.gone` is `display: none`, which zeroes it again.
    // jsdom has no layout to do either, so both are stood in for the same way the browser reports
    // them: `scrollTop` at zero, with a scroll event on the box.
    const props = (tab: ConsoleTab | null) =>
      panelProps({ messages: [userMsg, reply("m1")], consoleTab: tab }, true, false);
    const view = render(<Panel {...props(null)} />);
    const el = view.container.querySelector(".history") as HTMLDivElement;
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: 500 });
    Object.defineProperty(el, "clientHeight", { configurable: true, value: 100 });

    // A reader well up the log, reading rather than following.
    el.scrollTop = 100;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props("appearance")} />);
    el.scrollTop = 0;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props(null)} />);
    expect(el.scrollTop).toBe(100);

    // A reader who was AT the tail comes back to the tail, which is not the same line: a reply can
    // land while the console is up, and following the stream is what they asked for.
    el.scrollTop = 470;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props("shortcuts")} />);
    el.scrollTop = 0;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props(null)} />);
    expect(el.scrollTop).toBe(500);
  });

  it("keeps the leaving console on the tab it was showing, instead of flashing the first one", () => {
    const props = (tab: ConsoleTab | null) => panelProps({ consoleTab: tab }, true, false);
    const view = render(<Panel {...props("shortcuts")} />);
    expect(view.container.querySelector(".tabpane.on")?.getAttribute("aria-label")).toBe(
      "Chords",
    );
    // Closing keeps the console mounted for one morph so it can fade out. Its tab is already null
    // by then, and the fallback for that was the FIRST tab, so leaving from the shortcuts drew the
    // appearance pane over the one the user was looking at and took it away with the fade.
    view.rerender(<Panel {...props(null)} />);
    const leaving = view.container.querySelector(".view.out");
    expect(leaving?.querySelector(".tabpane.on")?.getAttribute("aria-label")).toBe("Chords");
  });

  it("marks the log bare only while the empty state is the whole of it", () => {
    // `.log.bare` is what stops the opening screen scrolling: the column may then be shorter than
    // its content, and clips instead of offering a bar for a picture with no more of it below.
    const log = (over: Partial<OverlayState>) =>
      renderPanel(over, true, false).container.querySelector(".log")?.className;
    expect(log({})).toBe("log bare");
    expect(log({ messages: [userMsg] })).toBe("log");
    // An approval card with no messages is still something to scroll to, so the log stays a log.
    expect(
      log({
        pendingConfirm: {
          confirmId: "c1",
          toolName: "email.send",
          argumentsJson: "{}",
          reason: "outbound",
        },
      }),
    ).toBe("log");
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
    expect(screen.getByRole("tabpanel", { name: "Chords" })).toBeInTheDocument();
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
    expect(hint("new line")?.querySelectorAll("b")).toHaveLength(2);
    expect(hint("new line")?.querySelector("b")?.textContent).toBe("Shift");
    expect(hint("new line")?.querySelectorAll("b.key")).toHaveLength(1);
    for (const cap of hint("new line")?.querySelectorAll("b.key") ?? []) {
      expect(cap.querySelectorAll("svg")).toHaveLength(1);
    }
    expect(hint("send")?.querySelectorAll("b.key")).toHaveLength(1);
    // Matched on "N new" rather than "new", which "new line" would answer to first.
    expect([...(hint("N new")?.querySelectorAll("b") ?? [])].map((b) => b.textContent)).toEqual([
      "Ctrl",
      "N",
    ]);
  });

  it("keeps the still edge exactly the panel it always was: no edge layers, no flag", () => {
    const { container } = renderPanel({}, true, false);
    expect(container.querySelector(".edge")).toBeNull();
    expect(screen.getByRole("dialog").className).not.toContain("edge-live");
  });

  it("hands a liquid edge the panel's face and mounts its layers", () => {
    const { container } = render(<Panel {...panelProps({}, true, false)} edge={LUCID} />);
    expect(screen.getByRole("dialog").className).toContain("edge-live");
    const slab = container.querySelector(".edge-glass") as HTMLElement;
    expect(slab.style.clipPath).toContain("path(");
  });

  it("tells the edge a turn is running, which is what deepens the liquid", () => {
    const streaming: Message = { ...reply("live"), streaming: true };
    const { container } = render(
      <Panel {...panelProps({ messages: [userMsg, streaming] }, true, false)} edge={LUCID} />,
    );
    expect(container.querySelector(".edge")?.className).toContain("edge-working");
  });
});
