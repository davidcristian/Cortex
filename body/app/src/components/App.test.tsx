import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { App } from "./App";

const activate = () => {
  act(() => {
    window.dispatchEvent(new Event("cortex:activate"));
  });
};

/** Render App with a pinned session id, flushing the mount chat-list load. */
async function renderApp(bridge: FakeBridge) {
  render(<App bridge={bridge} newSessionId={() => "s1"} />);
  await act(async () => {});
}

describe("App", () => {
  it("applies a theme, toggles it, and summons the overlay on the host activate event", async () => {
    await renderApp(new FakeBridge());
    expect(document.documentElement.dataset.theme).toBe("light");
    const toggle = screen.getByLabelText("Toggle theme");
    fireEvent.click(toggle);
    expect(document.documentElement.dataset.theme).toBe("dark");
    fireEvent.click(toggle);
    expect(document.documentElement.dataset.theme).toBe("light");
    activate();
    expect(screen.getByRole("dialog").className).toContain("open");
  });

  it("streams a submitted turn through the bridge on the minted session id", async () => {
    const bridge = new FakeBridge();
    await renderApp(bridge);
    activate();
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "hi" } });
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    expect(bridge.calls).toEqual([{ sessionId: "s1", text: "hi" }]);
  });

  it("a press on the bare stage dismisses the open panel; presses inside do not", async () => {
    await renderApp(new FakeBridge());
    activate();
    const stage = document.querySelector(".stage") as HTMLElement;
    // Inside the panel the press bubbles up with a different target and passes through.
    fireEvent.mouseDown(screen.getByLabelText("Message"));
    expect(screen.getByRole("dialog", { name: "Cortex" }).className).toContain("open");
    // The bare stage around the panel is the click-away surface.
    fireEvent.mouseDown(stage);
    expect(screen.getByRole("dialog", { hidden: true }).className).not.toContain("open");
    // Hidden already: another stage press is a no-op.
    fireEvent.mouseDown(stage);
    expect(screen.getByRole("dialog", { hidden: true }).className).not.toContain("open");
  });
});
