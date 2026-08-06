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

    // The ack rides the bridge in the frame the check is pressed. Nothing the user asked for
    // waits on an animation: the card's own roll is what lags, and the stack holds the row for
    // the length of it (`overlay/usePresence.ts`).
    fireEvent.click(screen.getByLabelText("Dismiss reminder"));
    expect(bridge.acks).toEqual(["r-1"]);
    await act(async () => {});
    expect(screen.queryByText("Stand-up in 10 minutes")).toBeNull();
  });

  it("lands the caret in the composer when a chat arrives on a row that leaves with it", async () => {
    // The whole path, door to caret: the row is pressed, the switcher rolls shut, the row stops
    // existing, and the browser has nowhere to put focus but `<body>`, one Tab from the top of the
    // page. The chat that arrived takes it instead (`overlayState`'s arrival, `Composer`).
    const bridge = new FakeBridge();
    bridge.sessions = [
      { sessionId: "s1", title: "About cats", preview: "p1", lastActivityUnixMs: 2, pinned: false },
      { sessionId: "s2", title: "About swaps", preview: "p2", lastActivityUnixMs: 1, pinned: false },
    ];
    bridge.messagesBySession = { s2: [{ role: "user", text: "about swaps", turnId: "t", atUnixMs: 1 }] };
    await renderApp(bridge);
    activate();
    await act(async () => {});
    fireEvent.click(screen.getByLabelText("Recent chats"));
    const rows = [...document.querySelectorAll<HTMLElement>(".switcher-item")];
    const row = rows[1] as HTMLElement;
    row.focus();
    expect(document.activeElement).toBe(row);
    fireEvent.click(row);
    await act(async () => {});
    expect(screen.getByText("about swaps")).toBeTruthy();
    expect(row).not.toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByLabelText("Message"));
  });

  it("swaps the reminder stack in with a new chat instead of rolling it over the old one", async () => {
    const bridge = new FakeBridge();
    bridge.reminders = [
      {
        reminderId: "r-1",
        text: "Stand-up in 10 minutes",
        firedAtUnixMs: Date.now() - 60_000,
        recurring: false,
        tainted: false,
        sessionId: "",
      },
    ];
    // A real mint per chat: with one pinned id the session never changes and the swap under test
    // (the stack keyed to the chat it belongs to) could not happen at all.
    let minted = 0;
    render(<App bridge={bridge} newSessionId={() => `s${++minted}`} />);
    await act(async () => {});
    activate();
    await act(async () => {});
    // A conversation on screen: the stack is shut behind it.
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "hi" } });
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    await act(async () => {});
    // Minting a new chat is a content swap, not a section toggle: the stack must arrive WITH the
    // emptied panel, in the panel's own single ease. A roll would announce itself (Collapse says
    // out loud that it has begun and ended), and the panel would follow the roll instead, which
    // is the two-motion jump the maintainer caught on a full chat.
    const rolls: string[] = [];
    const heard = (event: Event) => rolls.push(event.type);
    document.addEventListener("cortex:morphstart", heard);
    document.addEventListener("cortex:morphend", heard);
    fireEvent.click(screen.getByLabelText("New chat"));
    document.removeEventListener("cortex:morphstart", heard);
    document.removeEventListener("cortex:morphend", heard);
    expect(screen.getByText("Stand-up in 10 minutes")).toBeTruthy();
    expect(rolls).toEqual([]);
  });
});
