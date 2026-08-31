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
    // The pending request was consumed, so a remount does not summon a second time.
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
    // The bare stage around the panel is what dismisses on a press.
    fireEvent.mouseDown(stage);
    expect(screen.getByRole("dialog", { hidden: true }).className).not.toContain("open");
    // With the panel already hidden, another stage press does nothing.
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
    // Nothing is read into a window that is not on screen, the body sitting resident in the tray.
    expect(bridge.reminderListCalls).toBe(0);

    activate();
    await act(async () => {});
    expect(screen.getByText("Stand-up in 10 minutes")).toBeTruthy();
    expect(screen.getByText("repeats")).toBeTruthy();

    // The ack crosses the bridge in the frame the check is pressed, so no write waits on an
    // animation. Only the card's roll lags, and the stack holds the row for the length of it
    // (`overlay/usePresence.ts`).
    fireEvent.click(screen.getByLabelText("Dismiss reminder"));
    expect(bridge.acks).toEqual(["r-1"]);
    await act(async () => {});
    expect(screen.queryByText("Stand-up in 10 minutes")).toBeNull();
  });

  it("lands the caret in the composer when a chat arrives on a row that leaves with it", async () => {
    // The whole path from press to caret: the row is pressed, the switcher rolls shut, the row
    // stops existing, and the browser has nowhere to put focus but `<body>`, one Tab from the top
    // of the page. The chat that arrived takes it instead (`overlayState`'s arrival, `Composer`).
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

  it("keeps the caret in the switcher for a delete that swaps nothing", async () => {
    // The other half of that rule, end to end: deleting a chat that is not the one on screen
    // replaces no conversation, so `arrival` does not change and the composer is the wrong place
    // for the caret. The reader is managing chats and stays in the list, on the same control one
    // row down (`overlay/rowCaret.ts`). The write is a real round trip through the bridge, so this
    // also holds that the caret does not wait on it.
    const bridge = new FakeBridge();
    bridge.sessions = [
      { sessionId: "s1", title: "About cats", preview: "p1", lastActivityUnixMs: 3, pinned: false },
      { sessionId: "s2", title: "About swaps", preview: "p2", lastActivityUnixMs: 2, pinned: false },
      { sessionId: "s3", title: "About rain", preview: "p3", lastActivityUnixMs: 1, pinned: false },
    ];
    await renderApp(bridge);
    activate();
    await act(async () => {});
    fireEvent.click(screen.getByLabelText("Recent chats"));
    fireEvent.click(screen.getByLabelText("Delete About swaps"));
    // The confirm opens with focus on cancel rather than on the control that would delete.
    expect(document.activeElement).toBe(screen.getByLabelText("Cancel delete"));
    fireEvent.click(screen.getByLabelText("Confirm delete About swaps"));
    expect(document.activeElement).toBe(screen.getByLabelText("Delete About rain"));
    await act(async () => {});
    expect(bridge.deletes).toEqual(["s2"]);
    expect(document.activeElement).toBe(screen.getByLabelText("Delete About rain"));
    expect(document.activeElement).not.toBe(screen.getByLabelText("Message"));
  });

  it("hands the caret to the chats button when the reader closes the list from inside it", async () => {
    // The third case, end to end: no chat arrives and no row moves, the section the caret is in is
    // simply removed. Measured at 900x900 before the rule, the caret stayed on the pencil through
    // the 300ms roll and read `<body>` at 353ms, one Tab from the top of the document.
    const bridge = new FakeBridge();
    bridge.sessions = [
      { sessionId: "s1", title: "About cats", preview: "p1", lastActivityUnixMs: 2, pinned: false },
      { sessionId: "s2", title: "About swaps", preview: "p2", lastActivityUnixMs: 1, pinned: false },
    ];
    await renderApp(bridge);
    activate();
    await act(async () => {});
    fireEvent.click(screen.getByLabelText("Recent chats"));
    const pencil = screen.getByLabelText("Rename About swaps");
    pencil.focus();
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    await act(async () => {});
    expect(pencil).not.toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByLabelText("Recent chats"));
    // The caret came back out of the list rather than into the conversation, because the composer
    // receives it only when a chat arrives and none did here.
    expect(document.activeElement).not.toBe(screen.getByLabelText("Message"));
  });

  it("says what the list holds when the key opens it, and nothing when the button does", async () => {
    // The whole path for the opening direction, which the closing rule above left unchanged.
    // Measured over thirteen entry points, opening the switcher moved no caret and raised no live
    // region anywhere, so a reader who pressed Ctrl+K got no feedback at all. The key announces the
    // list and the header's button does not, because pressing the button reads its own
    // `aria-expanded` back under the caret. This test fails if either one takes the other's
    // behaviour.
    const bridge = new FakeBridge();
    bridge.sessions = [
      { sessionId: "s1", title: "About cats", preview: "p1", lastActivityUnixMs: 2, pinned: false },
      { sessionId: "s2", title: "About swaps", preview: "p2", lastActivityUnixMs: 1, pinned: false },
    ];
    await renderApp(bridge);
    activate();
    await act(async () => {});
    const region = document.querySelector(".announcer");
    const chats = screen.getByLabelText("Recent chats");
    fireEvent.click(chats);
    await act(async () => {});
    expect(chats.getAttribute("aria-expanded")).toBe("true");
    expect(region?.textContent).toBe("");
    fireEvent.click(chats);
    await act(async () => {});
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    await act(async () => {});
    expect(chats.getAttribute("aria-expanded")).toBe("true");
    expect(region?.textContent).toBe("Recent chats open. 2 chats.");
    // The caret is where it was, since only the live region changed.
    expect(document.activeElement).toBe(screen.getByLabelText("Message"));
    // Closing announces nothing, because the region carries what the list holds and not its state.
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    await act(async () => {});
    expect(region?.textContent).toBe("Recent chats open. 2 chats.");
  });

  it("hands the caret to the field when an example prompt takes the empty state away", async () => {
    // The same rule from the other side: pressing a chip unmounts the chip, and it is in no list,
    // so there is no next row to take the caret. Measured at 900x900 before this, the caret read
    // `<body>` at 39ms, with the reminder stack removed in the same commit.
    const bridge = new FakeBridge();
    await renderApp(bridge);
    activate();
    await act(async () => {});
    const chip = screen.getByText("Summarize my unread email");
    chip.focus();
    expect(document.activeElement).toBe(chip);
    fireEvent.click(chip);
    await act(async () => {});
    expect(bridge.calls).toEqual([{ sessionId: "s1", text: "Summarize my unread email" }]);
    expect(chip).not.toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByLabelText("Message"));
  });

  it("closes the list under a half-typed sentence without touching the caret in it", async () => {
    // The other half of that rule. Ctrl+K is a global key, so it is pressed as often from the
    // composer as from the list, and a reader who is writing must not be taken out of the sentence
    // to be told that a list they had no caret in has closed.
    const bridge = new FakeBridge();
    bridge.sessions = [
      { sessionId: "s1", title: "About cats", preview: "p1", lastActivityUnixMs: 2, pinned: false },
    ];
    await renderApp(bridge);
    activate();
    await act(async () => {});
    fireEvent.click(screen.getByLabelText("Recent chats"));
    const field = screen.getByLabelText("Message") as HTMLTextAreaElement;
    fireEvent.change(field, { target: { value: "half a question" } });
    field.focus();
    field.setSelectionRange(4, 4);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    await act(async () => {});
    expect(document.activeElement).toBe(field);
    expect([field.selectionStart, field.selectionEnd]).toEqual([4, 4]);
  });

  it("keeps each chat's half-typed question with the chat it was typed into", async () => {
    // The whole path, end to end: the field, the controller, the reducer and a real swap through
    // the bridge. Before this the composer held one text for the whole overlay and every way in
    // carried it across, so "half a question" typed in the fresh chat was still in the field, caret
    // and all, once another conversation had loaded around it, and the caret landing there made it
    // the first thing a reader met in the arriving chat.
    const bridge = new FakeBridge();
    bridge.sessions = [
      { sessionId: "s1", title: "About cats", preview: "p1", lastActivityUnixMs: 2, pinned: false },
      { sessionId: "s2", title: "About swaps", preview: "p2", lastActivityUnixMs: 1, pinned: false },
    ];
    bridge.messagesBySession = { s2: [{ role: "user", text: "about swaps", turnId: "t", atUnixMs: 1 }] };
    let minted = 0;
    render(<App bridge={bridge} newSessionId={() => `n${++minted}`} />);
    await act(async () => {});
    activate();
    await act(async () => {});
    const field = () => screen.getByLabelText("Message") as HTMLTextAreaElement;
    const openRow = async (title: string) => {
      fireEvent.click(screen.getByLabelText("Recent chats"));
      const row = [...document.querySelectorAll<HTMLElement>(".switcher-item")].find((item) =>
        item.textContent?.includes(title),
      ) as HTMLElement;
      fireEvent.click(row);
      await act(async () => {});
    };
    // The panel opened on the adopted chat, About cats. A question started in it:
    fireEvent.change(field(), { target: { value: "half a question" } });
    // Ctrl+↓ cycles to the next stored chat: the arriving conversation brings its own empty field.
    fireEvent.keyDown(window, { key: "ArrowDown", ctrlKey: true });
    await act(async () => {});
    expect(screen.getByText("about swaps")).toBeTruthy();
    expect(field().value).toBe("");
    // A sentence started here stays with this chat, and Ctrl+N has no stored draft to restore, so
    // the fresh chat arrives empty and neither sentence follows it in.
    fireEvent.change(field(), { target: { value: "and a thought about swaps" } });
    fireEvent.keyDown(window, { key: "n", ctrlKey: true });
    await act(async () => {});
    expect(field().value).toBe("");
    // Both drafts are still with the chats they were written in, whichever way those are reopened.
    await openRow("About swaps");
    expect(field().value).toBe("and a thought about swaps");
    await openRow("About cats");
    expect(field().value).toBe("half a question");
    // Sending a draft spends it, so the field is empty on the next visit to that chat.
    fireEvent.keyDown(field(), { key: "Enter" });
    await act(async () => {});
    expect(bridge.calls.at(-1)).toEqual({ sessionId: "s1", text: "half a question" });
    await openRow("About swaps");
    await openRow("About cats");
    expect(field().value).toBe("");
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
    // A distinct id per new chat: with one pinned id the session never changes, so the remount
    // under test (the stack keyed to the chat it belongs to) could not happen.
    let minted = 0;
    render(<App bridge={bridge} newSessionId={() => `s${++minted}`} />);
    await act(async () => {});
    activate();
    await act(async () => {});
    // With a conversation on screen the stack is shut behind it.
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "hi" } });
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    await act(async () => {});
    // Minting a new chat is a content swap rather than a section toggle, so the stack arrives with
    // the emptied panel in the panel's own single ease. A roll would dispatch its start and end
    // events and the panel would follow the roll instead, which is the two-motion jump the
    // maintainer caught on a full chat.
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
