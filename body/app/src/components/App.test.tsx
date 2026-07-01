import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { App } from "./App";

const activate = () => {
  act(() => {
    window.dispatchEvent(new Event("cortex:activate"));
  });
};

describe("App", () => {
  it("applies a theme, toggles it, and summons the overlay on the host activate event", () => {
    render(<App bridge={new FakeBridge()} sessionId="s1" />);
    expect(document.documentElement.dataset.theme).toBe("light");
    const toggle = screen.getByLabelText("Toggle theme");
    fireEvent.click(toggle);
    expect(document.documentElement.dataset.theme).toBe("dark");
    fireEvent.click(toggle);
    expect(document.documentElement.dataset.theme).toBe("light");
    activate();
    expect(screen.getByRole("dialog").className).toContain("open");
  });

  it("streams a submitted turn through the bridge", () => {
    const bridge = new FakeBridge();
    render(<App bridge={bridge} sessionId="s1" />);
    activate();
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "hi" } });
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    expect(bridge.calls).toEqual([{ sessionId: "s1", text: "hi" }]);
  });
});
