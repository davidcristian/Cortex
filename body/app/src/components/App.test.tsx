import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { requestActivation, takePendingActivation } from "../overlay/activation";
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
  it("opens for an activation that arrived before it had a listener", async () => {
    // The real ordering on both paths: the browser build self-summons on load and the host can
    // emit the hotkey while the webview is still mounting, both before React flushes the passive
    // effect that listens. The request waits rather than being dropped.
    const bridge = new FakeBridge();
    requestActivation();
    await renderApp(bridge);
    expect(screen.getByRole("dialog").className).toContain("open");
    // …and it was consumed, so a remount does not summon a second time.
    expect(takePendingActivation()).toBe(false);
  });

  it("leaves the overlay hidden when nothing asked for it", async () => {
    takePendingActivation();
    await renderApp(new FakeBridge());
    expect(screen.getByRole("dialog", { hidden: true }).className).not.toContain("open");
  });

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

  it("surfaces due reminders on summon and acks the one the user dismisses", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [
      {
        reminderId: "r-1",
        text: "Stand-up in 10 minutes",
        firedAtUnixMs: Date.now() - 60_000,
        recurring: true,
        tainted: false,
        sessionId: "s1",
      },
    ];
    await renderApp(bridge);
    // Nothing is pulled into a window nobody is looking at (the body sits resident in the tray).
    expect(bridge.reminderListCalls).toBe(0);

    activate();
    await act(async () => {});
    expect(screen.getByText("Stand-up in 10 minutes")).toBeTruthy();
    expect(screen.getByText("repeats")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("Dismiss reminder"));
    await act(async () => {});
    expect(bridge.acks).toEqual(["r-1"]);
    expect(screen.queryByText("Stand-up in 10 minutes")).toBeNull();
  });
});
