import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DueReminder } from "../bridge/types";
import { LUCID, STILL } from "../edge/edges";
import { MULL } from "../mark/marks";
import { parkDraft } from "../overlay/drafts";
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
  drafts: {},
  reminders: [],
  link: INITIAL_LINK,
  capture: null,
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
  onDraft?: (text: string) => void;
  onDismiss?: () => void;
  onNewChat?: () => void;
  onToggleSwitcher?: () => void;
  onSelectSession?: (sessionId: string) => void;
  onRenameSession?: (sessionId: string, title: string) => void;
  onDeleteSession?: (sessionId: string) => void;
  onHoistSession?: (sessionId: string, hoisted: boolean) => void;
  onRespondConfirm?: (confirmId: string, approved: boolean) => void;
  onDismissReminder?: (reminder: DueReminder) => void;
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
    onDraft: handlers.onDraft ?? vi.fn(),
    onStop: vi.fn(),
    onDismiss: handlers.onDismiss ?? vi.fn(),
    onNewChat: handlers.onNewChat ?? vi.fn(),
    onToggleSwitcher: handlers.onToggleSwitcher ?? vi.fn(),
    onSelectSession: handlers.onSelectSession ?? vi.fn(),
    onRenameSession: handlers.onRenameSession ?? vi.fn(),
    onDeleteSession: handlers.onDeleteSession ?? vi.fn(),
    onHoistSession: handlers.onHoistSession ?? vi.fn(),
    onRespondConfirm: handlers.onRespondConfirm ?? vi.fn(),
    onDismissReminder: handlers.onDismissReminder ?? vi.fn(),
  };
}

function renderPanel(over: Partial<OverlayState>, open: boolean, dark: boolean, handlers: Handlers = {}) {
  return render(<Panel {...panelProps(over, open, dark, handlers)} />);
}

/** The panel with the reducer's draft half wired back up. */
function LivePanel({ props }: { readonly props: ReturnType<typeof panelProps> }) {
  const [drafts, setDrafts] = useState(props.state.drafts);
  return (
    <Panel
      {...props}
      state={{ ...props.state, drafts }}
      onDraft={(text) => setDrafts((held) => parkDraft(held, props.state.sessionId, text))}
    />
  );
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
    expect(dot.previousElementSibling?.textContent).toBe("My chat");
    expect(dot.nextElementSibling).toBe(screen.getByLabelText("Recent chats"));
  });

  it("appears with the capture ring against the title, so nothing on the row moves", () => {
    renderPanel({ capture: "asked" }, true, false);
    const [capture, link] = screen.getAllByRole("status");
    expect(capture?.className).toBe("capturedot");
    expect(link?.className).toContain("linkdot");
    expect(capture).toHaveAccessibleName(
      "The assistant asked to look at your screen during this reply",
    );
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
          { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000, hoisted: false },
        ],
      },
      true,
      false,
      { onSelectSession },
    );
    fireEvent.click(screen.getByText("First chat"));
    expect(onSelectSession).toHaveBeenCalledWith("c1", false);
  });

  it("threads the delete handler to the switcher: confirming a row's trash deletes it", () => {
    const onDeleteSession = vi.fn();
    renderPanel(
      {
        switcherOpen: true,
        sessions: [
          { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000, hoisted: false },
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

  it("threads the hoist handler to the switcher: clicking a row's toggle hoists it", () => {
    const onHoistSession = vi.fn();
    renderPanel(
      {
        switcherOpen: true,
        sessions: [
          { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000, hoisted: false },
        ],
      },
      true,
      false,
      { onHoistSession },
    );
    fireEvent.click(screen.getByLabelText("Hoist First chat"));
    expect(onHoistSession).toHaveBeenCalledWith("c1", true);
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
    expect(container.querySelector(".history")?.contains(stack)).toBe(false);
    fireEvent.click(screen.getByText("open chat"));
    expect(onSelectSession).toHaveBeenCalledWith("c9", true);
    fireEvent.click(screen.getByLabelText("Dismiss reminder"));
    expect(onDismissReminder).toHaveBeenCalledWith(
      expect.objectContaining({ reminderId: "r-1", firedAtUnixMs: 1000 }),
    );
  });

  it("opens the console on the tab each gesture names: the sliders and the mark on appearance", () => {
    const onToggleConsole = vi.fn();
    renderPanel({}, true, false, { onToggleConsole });
    fireEvent.click(screen.getByLabelText("Settings"));
    expect(onToggleConsole).toHaveBeenCalledWith("appearance");
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
    expect(container.querySelector(".view.gone")).not.toBeNull();
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

    view.rerender(<Panel {...props("shortcuts")} />);
    expect(view.container.querySelectorAll(".pane")).toHaveLength(1);
    expect(view.container.querySelector(".view.out")).toBeNull();
    expect(view.container.querySelectorAll(".tabpane")).toHaveLength(2);
  });

  it("keeps the inactive tab's box but exposes neither it nor its content", () => {
    const props = (tab: ConsoleTab) => panelProps({ consoleTab: tab }, true, false);
    const view = render(<Panel {...props("shortcuts")} />);
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
    view.rerender(<Panel {...props("appearance")} />);
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Face" }));
    view.rerender(<Panel {...props(null)} />);
    expect(document.activeElement).toBe(field);
  });

  it("keeps the rise-and-sink for the chat leaving, which shares no chrome with the console", () => {
    const props = (tab: ConsoleTab | null) => panelProps({ consoleTab: tab }, true, false);
    const view = render(<Panel {...props(null)} />);
    view.rerender(<Panel {...props("appearance")} />);
    expect(view.container.querySelector(".view.out")?.className).toBe("view out");
    expect(view.container.querySelector(".views > div:not(.out):not(.gone)")?.className).toBe(
      "view",
    );
  });

  it("holds the view it is leaving on screen for one morph, out of the flow", () => {
    const props = (over: Partial<OverlayState>) => panelProps(over, true, false);
    const view = render(<Panel {...props({ consoleTab: "shortcuts" })} />);
    expect(view.container.querySelector(".view.out")).toBeNull();
    view.rerender(<Panel {...props({})} />);
    const leaving = view.container.querySelector(".view.out");
    expect(leaving?.textContent).toContain("Switcher");
    expect(screen.getByLabelText("Recent chats")).toBeInTheDocument();
  });

  it("takes the leaving view out of the tab order for as long as it is out of the tree's", () => {
    const props = (over: Partial<OverlayState>) => panelProps(over, true, false);
    const view = render(<Panel {...props({ consoleTab: "shortcuts" })} />);
    const views = () => [...view.container.querySelectorAll(".views > .view")];
    expect(views().map((pane) => pane.hasAttribute("inert"))).toEqual([true, false]);

    view.rerender(<Panel {...props({})} />);
    const leaving = view.container.querySelector(".view.out") as HTMLElement;
    expect(leaving.getAttribute("aria-hidden")).toBe("true");
    expect(leaving.hasAttribute("inert")).toBe(true);
    expect(view.container.querySelector(".views > .view:not(.out)")).not.toHaveAttribute("inert");
  });

  it("takes a dismissed panel out of the tab order, orb and hidden alike", () => {
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
    const empty = renderPanel({}, true, false).container;
    expect(empty.querySelector(".history > .log > .empty")).not.toBeNull();
    cleanup();
    const talking = renderPanel({ messages: [userMsg] }, true, false).container;
    expect(talking.querySelector(".history > .log > .bubble")).not.toBeNull();
  });

  it("sizes that floor off the invitation it is copying, while the invitation is on screen", () => {
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
    view.rerender(<Panel {...props([userMsg, reply("m1")])} />);
    expect(el.scrollTop).toBe(500);
    el.scrollTop = 100;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props([userMsg, reply("m1"), reply("m2")])} />);
    expect(el.scrollTop).toBe(100);
    el.scrollTop = 470;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props([userMsg, reply("m1"), reply("m2"), reply("m3")])} />);
    expect(el.scrollTop).toBe(500);
  });

  it("holds the tail when a growing draft eats the log's height, unless the reader scrolled up", () => {
    const view = render(<LivePanel props={panelProps({ messages: [userMsg, reply("m1")] }, true, false)} />);
    const el = view.container.querySelector(".history") as HTMLDivElement;
    const field = screen.getByLabelText("Message") as HTMLTextAreaElement;
    const pill = field.parentElement as HTMLDivElement;
    Object.defineProperty(field, "clientHeight", { configurable: true, value: 34 });
    Object.defineProperty(field, "scrollHeight", { configurable: true, get: () => 50 });
    Object.defineProperty(pill, "offsetHeight", { configurable: true, get: () => 90 });
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: 500 });
    Object.defineProperty(el, "clientHeight", { configurable: true, value: 100 });
    fireEvent.change(field, { target: { value: "a draft\nover two lines" } });
    expect(el.scrollTop).toBe(500);
    el.scrollTop = 100;
    fireEvent.scroll(el);
    Object.defineProperty(pill, "offsetHeight", { configurable: true, get: () => 130 });
    fireEvent.change(field, { target: { value: "a draft\nover two lines\nand a third" } });
    expect(el.scrollTop).toBe(100);
  });

  it("holds the log's place while a section rolls open in the chrome beside it", () => {
    const land = stubRoll();
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) =>
      frames.push(callback),
    );
    vi.stubGlobal("cancelAnimationFrame", () => undefined);
    const messages = [userMsg, reply("m1")];
    const props = (switcherOpen: boolean) => panelProps({ messages, switcherOpen }, true, false);
    const view = render(<Panel {...props(false)} />);
    const el = view.container.querySelector(".history") as HTMLDivElement;
    let seen = 293;
    Object.defineProperty(el, "scrollHeight", { configurable: true, get: () => 704 });
    Object.defineProperty(el, "clientHeight", { configurable: true, get: () => seen });
    el.scrollTop = 408;
    view.rerender(<Panel {...props(true)} />);
    frames[frames.length - 1]?.(0);
    expect(el.scrollTop).toBe(408);
    seen = 73;
    frames[frames.length - 1]?.(0);
    expect(el.scrollTop).toBe(628);
    land();
  });

  it("hands the log back its place after a trip to the console, ignoring the layout's scrolling", () => {
    const props = (tab: ConsoleTab | null) =>
      panelProps({ messages: [userMsg, reply("m1")], consoleTab: tab }, true, false);
    const view = render(<Panel {...props(null)} />);
    const el = view.container.querySelector(".history") as HTMLDivElement;
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: 500 });
    Object.defineProperty(el, "clientHeight", { configurable: true, value: 100 });

    el.scrollTop = 100;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props("appearance")} />);
    el.scrollTop = 0;
    fireEvent.scroll(el);
    view.rerender(<Panel {...props(null)} />);
    expect(el.scrollTop).toBe(100);

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
    view.rerender(<Panel {...props(null)} />);
    const leaving = view.container.querySelector(".view.out");
    expect(leaving?.querySelector(".tabpane.on")?.getAttribute("aria-label")).toBe("Chords");
  });

  it("marks the log bare only while the empty state is the whole of it", () => {
    const log = (over: Partial<OverlayState>) =>
      renderPanel(over, true, false).container.querySelector(".log")?.className;
    expect(log({})).toBe("log bare");
    expect(log({ messages: [userMsg] })).toBe("log");
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
    expect(hint("new line")?.querySelectorAll("b")).toHaveLength(2);
    expect(hint("new line")?.querySelector("b")?.textContent).toBe("Shift");
    expect(hint("new line")?.querySelectorAll("b.key")).toHaveLength(1);
    for (const cap of hint("new line")?.querySelectorAll("b.key") ?? []) {
      expect(cap.querySelectorAll("svg")).toHaveLength(1);
    }
    expect(hint("send")?.querySelectorAll("b.key")).toHaveLength(1);
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
