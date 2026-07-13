import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
      sheetOpen: false,
      pendingConfirm: null,
      seq: 0,
      touched: false,
      ...extra,
    },
    submit: vi.fn(),
    stop: vi.fn(),
    dismiss: vi.fn(),
    open: vi.fn(),
    newChat: vi.fn(),
    openSession: vi.fn(),
    cyclePrev: vi.fn(),
    cycleNext: vi.fn(),
    toggleSwitcher: vi.fn(),
    toggleSheet: vi.fn(),
    previewHover: vi.fn(),
    respondConfirm: vi.fn(),
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
  error: null,
};

function renderOverlay(controller: OverlayController, onToggleTheme: () => void = vi.fn()) {
  return render(<Overlay controller={controller} dark={false} onToggleTheme={onToggleTheme} />);
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
    renderOverlay(controller);
    expect(screen.getByText("the answer")).toBeInTheDocument();
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
        { sessionId: "c1", title: "First chat", preview: "hello", lastActivityUnixMs: 1000 },
      ],
    });
    renderOverlay(controller);
    fireEvent.click(screen.getByText("First chat"));
    expect(controller.openSession).toHaveBeenCalledWith("c1");
  });

  it("? toggles the shortcut sheet, except while typing in the composer", () => {
    const controller = fakeController("panel");
    renderOverlay(controller);
    fireEvent.keyDown(document.body, { key: "?" });
    expect(controller.toggleSheet).toHaveBeenCalledOnce();
    // In the composer a ? is just typing, never the sheet.
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "?" });
    expect(controller.toggleSheet).toHaveBeenCalledOnce();
  });

  it("Escape closes an open shortcut sheet instead of dismissing the panel", () => {
    const controller = fakeController("panel", [], { sheetOpen: true });
    renderOverlay(controller);
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(controller.toggleSheet).toHaveBeenCalledOnce();
    expect(controller.dismiss).not.toHaveBeenCalled();
  });

  it("forwards preview hover to the controller's pause latch", () => {
    const controller = fakeController("preview", [reply]);
    renderOverlay(controller);
    fireEvent.mouseEnter(screen.getByLabelText("Open reply"));
    expect(controller.previewHover).toHaveBeenCalledWith(true);
  });
});
