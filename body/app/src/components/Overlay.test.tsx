import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { STILL } from "../edge/edges";
import { MULL } from "../mark/marks";
import { INITIAL_LINK } from "../overlay/linkState";
import type { Message, OverlayState } from "../overlay/overlayState";
import type { OverlayController } from "../overlay/useOverlay";
import { Overlay } from "./Overlay";

function fakeController(
  mode: OverlayState["mode"],
  messages: readonly Message[] = [],
  extra: Partial<OverlayState> = {},
) {
  const controller: OverlayController = {
    state: {
      mode,
      sessionId: "s1",
      title: "t",
      messages,
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
      ...extra,
    },
    submit: vi.fn(),
    setDraft: vi.fn(),
    stop: vi.fn(),
    dismiss: vi.fn(),
    open: vi.fn(),
    newChat: vi.fn(),
    openSession: vi.fn(),
    renameSession: vi.fn(),
    deleteSession: vi.fn(),
    setSessionPinned: vi.fn(),
    cyclePrev: vi.fn(),
    cycleNext: vi.fn(),
    toggleSwitcher: vi.fn(),
    openConsole: vi.fn(),
    toggleConsole: vi.fn(),
    closeConsole: vi.fn(),
    previewHover: vi.fn(),
    respondConfirm: vi.fn(),
    dismissReminder: vi.fn(),
  };
  return controller;
}

const reply: Message = {
  id: "a",
  role: "assistant",
  content: "the answer",
  streaming: false,
  tool: null,
  status: null,
  statusState: null,
  thoughts: "",
  error: null,
};

function renderOverlay(controller: OverlayController, onToggleTheme: () => void = vi.fn()) {
  return render(
    <Overlay
      controller={controller}
      dark={false}
      mark={MULL}
      edge={STILL}
      themeName={null}
      onPickTheme={vi.fn()}
      onPickMark={vi.fn()}
      onPickEdge={vi.fn()}
      onToggleTheme={onToggleTheme}
    />,
  );
}

describe("Overlay", () => {
  it("routes to the panel with no orb or preview in panel mode", () => {
    renderOverlay(fakeController("panel"));
    expect(screen.getByRole("dialog").className).toContain("open");
    expect(screen.queryByLabelText(/Reopen/u)).toBeNull();
  });

  it("forwards the theme toggle to the panel header", () => {
    const onToggleTheme = vi.fn();
    renderOverlay(fakeController("panel"), onToggleTheme);
    fireEvent.click(screen.getByLabelText("Toggle theme"));
    expect(onToggleTheme).toHaveBeenCalledOnce();
  });

  it("shows the orb in orb mode and reopens on click", () => {
    const controller = fakeController("orb");
    renderOverlay(controller);
    fireEvent.click(screen.getByLabelText(/Reopen/u));
    expect(controller.open).toHaveBeenCalledOnce();
  });

  it("shows the preview with the latest reply and reopens on click", () => {
    const controller = fakeController("preview", [reply]);
    const { container } = renderOverlay(controller);
    // Asked of the card's own text box: the reply also stands in the always-mounted panel
    // behind it, as one plain text node now that a settled bubble is not word spans.
    expect(container.querySelector(".pv-b")?.textContent).toBe("the answer");
    fireEvent.click(screen.getByLabelText("Open reply"));
    expect(controller.open).toHaveBeenCalledOnce();
  });

  it("Escape dismisses when visible, but not when hidden", () => {
    const visible = fakeController("panel");
    const { unmount } = renderOverlay(visible);
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(visible.dismiss).toHaveBeenCalledOnce();
    unmount();
    const hidden = fakeController("hidden");
    renderOverlay(hidden);
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(hidden.dismiss).not.toHaveBeenCalled();
  });

  it("Ctrl+N and Cmd+N start a new chat; other keys and Ctrl+other are ignored", () => {
    const controller = fakeController("panel");
    renderOverlay(controller);
    fireEvent.keyDown(document.body, { key: "n", ctrlKey: true });
    fireEvent.keyDown(document.body, { key: "N", metaKey: true });
    expect(controller.newChat).toHaveBeenCalledTimes(2);
    fireEvent.keyDown(document.body, { key: "a" });
    fireEvent.keyDown(document.body, { key: "a", ctrlKey: true });
    expect(controller.newChat).toHaveBeenCalledTimes(2);
    expect(controller.dismiss).not.toHaveBeenCalled();
  });

  it("Ctrl+N announces the chat it mints and the header's pencil does not", () => {
    // One controller call, two doors, and the difference is the whole rule: a keystroke names
    // nothing, so the fresh chat is announced, while the pencil is labelled "New chat" and
    // would be handing the reader back the label they just pressed (`overlay/notice.ts`).
    const controller = fakeController("panel");
    renderOverlay(controller);
    fireEvent.keyDown(document.body, { key: "n", ctrlKey: true });
    expect(controller.newChat).toHaveBeenCalledWith(true);
    fireEvent.click(screen.getByLabelText("New chat"));
    expect(controller.newChat).toHaveBeenLastCalledWith(false);
  });

  it("keeps the live region outside the panel, which is out of the tree while dismissed", () => {
    // The cycle keys are global, so a press can open the panel and swap the chat in one commit.
    // A region inside the panel would arrive in the accessibility tree in the same frame as the
    // words it wants read, out of a subtree that was `inert` until that frame. Reddens if the
    // announcer is ever moved under the panel.
    const controller = fakeController("hidden", [], {
      notice: { text: "Switched to Everything about model swaps.", count: 1 },
    });
    const { container } = renderOverlay(controller);
    const region = container.querySelector(".announcer");
    const panel = container.querySelector(".panel");
    expect(region?.textContent).toBe("Switched to Everything about model swaps.");
    expect(panel?.hasAttribute("inert")).toBe(true);
    expect(panel?.contains(region ?? null)).toBe(false);
  });

  it("Ctrl+K toggles the switcher and Ctrl+↑/↓ cycle chats", () => {
    const controller = fakeController("panel");
    renderOverlay(controller);
    fireEvent.keyDown(document.body, { key: "k", ctrlKey: true });
    expect(controller.toggleSwitcher).toHaveBeenCalledOnce();
    fireEvent.keyDown(document.body, { key: "ArrowUp", ctrlKey: true });
    expect(controller.cyclePrev).toHaveBeenCalledOnce();
    fireEvent.keyDown(document.body, { key: "ArrowDown", metaKey: true });
    expect(controller.cycleNext).toHaveBeenCalledOnce();
    // Arrows without the modifier are ignored (they scroll the history).
    fireEvent.keyDown(document.body, { key: "ArrowUp" });
    expect(controller.cyclePrev).toHaveBeenCalledOnce();
  });

  it("all four chords still reach the overlay from the composer, whose text survives them", () => {
    // The half of the rule that has to keep working (`overlay/fieldKeys.ts`): a field HOLDS a chord
    // only when the chord would throw its text away, and this one keeps every keystroke under the
    // chat it was typed into. It is also where a summon lands, so it is where these keys are
    // pressed from. Reddens if the guard is ever widened from the editor to fields in general.
    const controller = fakeController("panel");
    renderOverlay(controller);
    const composer = screen.getByLabelText("Message");
    fireEvent.keyDown(composer, { key: "n", ctrlKey: true });
    fireEvent.keyDown(composer, { key: "k", ctrlKey: true });
    fireEvent.keyDown(composer, { key: "ArrowUp", ctrlKey: true });
    fireEvent.keyDown(composer, { key: "ArrowDown", ctrlKey: true });
    expect(controller.newChat).toHaveBeenCalledOnce();
    expect(controller.toggleSwitcher).toHaveBeenCalledOnce();
    expect(controller.cyclePrev).toHaveBeenCalledOnce();
    expect(controller.cycleNext).toHaveBeenCalledOnce();
  });

  it("routes a card answer to the controller's respondConfirm", () => {
    const controller = fakeController("panel", [], {
      pendingConfirm: {
        confirmId: "c-1",
        toolName: "send_email",
        argumentsJson: '{"to":"ada@example.com"}',
        reason: "outbound",
      },
    });
    renderOverlay(controller);
    fireEvent.click(screen.getByText("Deny"));
    expect(controller.respondConfirm).toHaveBeenCalledWith("c-1", false);
  });

  it("opens a chat from the switcher list", () => {
    const controller = fakeController("panel", [], {
      switcherOpen: true,
      sessions: [
        { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000, pinned: false },
      ],
    });
    renderOverlay(controller);
    fireEvent.click(screen.getByText("First chat"));
    expect(controller.openSession).toHaveBeenCalledWith("c1", false);
  });

  it("? opens the console on its shortcuts tab, except while typing in the composer", () => {
    const controller = fakeController("panel");
    renderOverlay(controller);
    fireEvent.keyDown(document.body, { key: "?" });
    expect(controller.toggleConsole).toHaveBeenCalledWith("shortcuts");
    // In the composer a ? is just typing, never the console.
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "?" });
    expect(controller.toggleConsole).toHaveBeenCalledOnce();
    // And in the switcher's rename editor, which is the overlay's other field and an `<input>`
    // rather than a textarea. The caret is put there by the pencil now (`overlay/rowCaret.ts`), so
    // this is a question somebody can be halfway through typing: measured at 900x900 before this,
    // "why?" left "why" in the field and the settings pane over the row being renamed.
    const editor = document.createElement("input");
    document.body.append(editor);
    fireEvent.keyDown(editor, { key: "?" });
    expect(controller.toggleConsole).toHaveBeenCalledOnce();
    editor.remove();
  });

  it("Escape leaves the console in ONE press from either tab, without dismissing the panel", () => {
    for (const tab of ["appearance", "shortcuts"] as const) {
      const controller = fakeController("panel", [], { consoleTab: tab });
      const { unmount } = renderOverlay(controller);
      fireEvent.keyDown(document.body, { key: "Escape" });
      // One console, so one Esc: the settings-then-shortcuts two-step is gone with the two sheets.
      expect(controller.closeConsole).toHaveBeenCalledOnce();
      expect(controller.dismiss).not.toHaveBeenCalled();
      unmount();
    }
  });

  it("forwards preview hover to the controller's pause latch", () => {
    const controller = fakeController("preview", [reply]);
    renderOverlay(controller);
    fireEvent.mouseEnter(screen.getByLabelText("Open reply"));
    expect(controller.previewHover).toHaveBeenCalledWith(true);
  });
});
