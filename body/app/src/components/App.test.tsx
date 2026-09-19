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

/** Render App with a fixed session id, flushing the mount chat-list load. */
async function renderApp(bridge: FakeBridge) {
  render(<App bridge={bridge} newSessionId={() => "s1"} />);
  await act(async () => {});
}

describe("App", () => {
  it("opens for an activation that arrived before it had a listener", async () => {
    const bridge = new FakeBridge();
    requestActivation();
    await renderApp(bridge);
    expect(screen.getByRole("dialog").className).toContain("open");
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
    fireEvent.mouseDown(screen.getByLabelText("Message"));
    expect(screen.getByRole("dialog", { name: "Cortex" }).className).toContain("open");
    fireEvent.mouseDown(stage);
    expect(screen.getByRole("dialog", { hidden: true }).className).not.toContain("open");
    fireEvent.mouseDown(stage);
    expect(screen.getByRole("dialog", { hidden: true }).className).not.toContain("open");
  });

  it("surfaces due reminders on summon and acks the one the user dismisses", async () => {
    const bridge = new FakeBridge();
    const due = {
      reminderId: "r-1",
      text: "Stand-up in 10 minutes",
      firedAtUnixMs: Date.now() - 60_000,
      recurring: true,
      tainted: false,
      sessionId: "s1",
    };
    bridge.reminders = [due];
    await renderApp(bridge);
    expect(bridge.reminderListCalls).toBe(0);

    activate();
    await act(async () => {});
    expect(screen.getByText("Stand-up in 10 minutes")).toBeTruthy();
    expect(screen.getByText("repeats")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("Dismiss reminder"));
    expect(bridge.acks).toEqual([{ reminderId: "r-1", firedAtUnixMs: due.firedAtUnixMs }]);
    await act(async () => {});
    expect(screen.queryByText("Stand-up in 10 minutes")).toBeNull();
  });

  it("lands the caret in the composer when a chat arrives on a row that leaves with it", async () => {
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
    expect(document.activeElement).toBe(screen.getByLabelText("Cancel delete"));
    fireEvent.click(screen.getByLabelText("Confirm delete About swaps"));
    expect(document.activeElement).toBe(screen.getByLabelText("Delete About rain"));
    await act(async () => {});
    expect(bridge.deletes).toEqual(["s2"]);
    expect(document.activeElement).toBe(screen.getByLabelText("Delete About rain"));
    expect(document.activeElement).not.toBe(screen.getByLabelText("Message"));
  });

  it("hands the caret to the chats button when the reader closes the list from inside it", async () => {
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
    expect(document.activeElement).not.toBe(screen.getByLabelText("Message"));
  });

  it("says what the list holds when the key opens it, and nothing when the button does", async () => {
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
    expect(document.activeElement).toBe(screen.getByLabelText("Message"));
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    await act(async () => {});
    expect(region?.textContent).toBe("Recent chats open. 2 chats.");
  });

  it("hands the caret to the field when an example prompt takes the empty state away", async () => {
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
    fireEvent.change(field(), { target: { value: "half a question" } });
    fireEvent.keyDown(window, { key: "ArrowDown", ctrlKey: true });
    await act(async () => {});
    expect(screen.getByText("about swaps")).toBeTruthy();
    expect(field().value).toBe("");
    fireEvent.change(field(), { target: { value: "and a thought about swaps" } });
    fireEvent.keyDown(window, { key: "n", ctrlKey: true });
    await act(async () => {});
    expect(field().value).toBe("");
    await openRow("About swaps");
    expect(field().value).toBe("and a thought about swaps");
    await openRow("About cats");
    expect(field().value).toBe("half a question");
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
    let minted = 0;
    render(<App bridge={bridge} newSessionId={() => `s${++minted}`} />);
    await act(async () => {});
    activate();
    await act(async () => {});
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "hi" } });
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    await act(async () => {});
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
