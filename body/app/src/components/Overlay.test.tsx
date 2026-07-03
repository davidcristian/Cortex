import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Message, OverlayState } from "../overlay/overlayState";
import type { OverlayController } from "../overlay/useOverlay";
import { Overlay } from "./Overlay";

function fakeController(mode: OverlayState["mode"], messages: readonly Message[] = []) {
  const controller: OverlayController = {
    state: { mode, title: "t", messages, seq: 0 },
    submit: vi.fn(),
    dismiss: vi.fn(),
    open: vi.fn(),
    newChat: vi.fn(),
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
});
