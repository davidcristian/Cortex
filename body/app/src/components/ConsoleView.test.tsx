import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { STILL } from "../edge/edges";
import { MULL } from "../mark/marks";
import { CONSOLE_TABS, type ConsoleTab } from "../overlay/overlayState";
import { ConsoleView, TAB_SPREAD_PX } from "./ConsoleView";

function renderConsole(
  tab: ConsoleTab,
  over: { onSelectTab?: (tab: ConsoleTab) => void; onClose?: () => void } = {},
) {
  return render(
    <ConsoleView
      tab={tab}
      themeName={null}
      mark={MULL}
      edge={STILL}
      animated={false}
      onPickTheme={vi.fn()}
      onPickMark={vi.fn()}
      onPickEdge={vi.fn()}
      onSelectTab={over.onSelectTab ?? vi.fn()}
      onClose={over.onClose ?? vi.fn()}
    />,
  );
}

/** The console wired to its own selection, which is what the panel does with it. */
function renderLive(start: ConsoleTab, onSelectTab?: (tab: ConsoleTab) => void) {
  function Live() {
    const [tab, setTab] = useState<ConsoleTab>(start);
    return (
      <ConsoleView
        tab={tab}
        themeName={null}
        mark={MULL}
        edge={STILL}
        animated={false}
        onPickTheme={vi.fn()}
        onPickMark={vi.fn()}
        onPickEdge={vi.fn()}
        onSelectTab={(next) => {
          onSelectTab?.(next);
          setTab(next);
        }}
        onClose={vi.fn()}
      />
    );
  }
  return render(<Live />);
}

/** The strip as the Tab key reaches it: which tab buttons are in the page's tab order. */
function stops() {
  return screen
    .getAllByRole("tab")
    .filter((tab) => tab.tabIndex >= 0)
    .map((tab) => tab.textContent);
}

/** jsdom has no layout, so the two tabs are given heights: the taller keeps the height the browser
 *  measures for the shortcut list, and the other is `spread()` px shorter. */
function stubTabHeights(spread: () => number) {
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockImplementation(function (
    this: HTMLElement,
  ) {
    if (!this.classList.contains("tabpane")) {
      return 0;
    }
    return this.getAttribute("aria-label") === "Face" ? 290 - spread() : 290;
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ConsoleView", () => {
  it("is one region with a strip of every tab, the showing one selected", () => {
    renderConsole("appearance");
    expect(screen.getByRole("region", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(CONSOLE_TABS.length);
    expect(screen.getByRole("tab", { name: "Face" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Chords" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("shows the appearance choices on one tab and the shortcut list on the other", () => {
    const { unmount } = renderConsole("appearance");
    expect(screen.getByRole("tabpanel", { name: "Face" })).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "Iris" })).toBeInTheDocument();
    expect(screen.queryByText("Chat switcher")).toBeNull();
    unmount();
    renderConsole("shortcuts");
    expect(screen.getByRole("tabpanel", { name: "Chords" })).toBeInTheDocument();
    expect(screen.getByText("Switcher")).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: "Iris" })).toBeNull();
  });

  it("takes focus onto the tab it is showing, since the strip it was clicked on is leaving", () => {
    renderConsole("shortcuts");
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Chords" }));
  });

  it("asks for a tab by name, including the one already showing (the strip cannot close it)", () => {
    const onSelectTab = vi.fn();
    renderConsole("appearance", { onSelectTab });
    fireEvent.click(screen.getByRole("tab", { name: "Chords" }));
    expect(onSelectTab).toHaveBeenCalledWith("shortcuts");
    fireEvent.click(screen.getByRole("tab", { name: "Face" }));
    expect(onSelectTab).toHaveBeenLastCalledWith("appearance");
  });

  it("holds one height for two close tabs, and lets the shorter go when they are not close", () => {
    let spread = TAB_SPREAD_PX;
    stubTabHeights(() => spread);
    const stack = () => document.querySelector(".tabstack") as HTMLElement;

    const held = renderConsole("appearance");
    expect(stack().classList.contains("apart")).toBe(false);
    held.unmount();

    spread = TAB_SPREAD_PX + 1;
    renderConsole("appearance");
    expect(stack().classList.contains("apart")).toBe(true);
    expect(stack().hasAttribute("data-measuring")).toBe(false);
  });

  it("points each face at the pane it is the handle for", () => {
    const { container } = renderConsole("appearance");
    for (const [label, pane] of [
      ["Face", "Appearance"],
      ["Chords", "Shortcuts"],
    ] as const) {
      const target = screen.getByRole("tab", { name: label }).getAttribute("aria-controls");
      const box = container.querySelector(`#${CSS.escape(target as string)}`);
      expect(box?.className).toContain("tabpane");
      expect(box?.getAttribute("aria-label")).toBe(label);
      expect(box?.textContent).toContain(pane === "Appearance" ? "Light" : "Switcher");
    }
  });

  it("is one stop in the tab order however many faces it has, and the stop is the one showing", () => {
    const { unmount } = renderConsole("appearance");
    expect(stops()).toEqual(["Face"]);
    unmount();
    renderConsole("shortcuts");
    expect(stops()).toEqual(["Chords"]);
  });

  it("moves along the strip on the arrows, selecting as it goes, and wraps at both ends", () => {
    const onSelectTab = vi.fn();
    renderLive("appearance", onSelectTab);
    const face = screen.getByRole("tab", { name: "Face" });
    const chords = screen.getByRole("tab", { name: "Chords" });

    fireEvent.keyDown(face, { key: "ArrowRight" });
    expect(onSelectTab).toHaveBeenLastCalledWith("shortcuts");
    expect(chords).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(chords);
    expect(stops()).toEqual(["Chords"]);

    fireEvent.keyDown(chords, { key: "ArrowRight" });
    expect(document.activeElement).toBe(face);
    expect(face).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(face, { key: "ArrowLeft" });
    expect(document.activeElement).toBe(chords);
    fireEvent.keyDown(chords, { key: "ArrowLeft" });
    expect(document.activeElement).toBe(face);
  });

  it("sends Home and End to the ends of the strip", () => {
    renderLive("appearance");
    const face = screen.getByRole("tab", { name: "Face" });
    const chords = screen.getByRole("tab", { name: "Chords" });
    fireEvent.keyDown(face, { key: "End" });
    expect(document.activeElement).toBe(chords);
    expect(chords).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(chords, { key: "Home" });
    expect(document.activeElement).toBe(face);
    expect(face).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(face, { key: "Home" });
    expect(document.activeElement).toBe(face);
  });

  it("keeps the keys it does not answer, so the panel's own chords still reach it", () => {
    const onSelectTab = vi.fn();
    renderLive("appearance", onSelectTab);
    const face = screen.getByRole("tab", { name: "Face" });
    for (const key of ["ArrowDown", "ArrowUp", "Escape", "k"]) {
      expect(fireEvent.keyDown(face, { key })).toBe(true);
    }
    expect(onSelectTab).not.toHaveBeenCalled();
    for (const key of ["ArrowRight", "ArrowLeft", "Home", "End"]) {
      expect(fireEvent.keyDown(screen.getByRole("tab", { selected: true }), { key })).toBe(false);
    }
  });

  it("takes the pane it is leaving out of the tab order in the frame it stops showing it", () => {
    const { container } = renderLive("appearance");
    const pane = (label: string) =>
      [...container.querySelectorAll(".tabpane")].find(
        (box) => box.getAttribute("aria-label") === label,
      ) as HTMLElement;
    expect(pane("Face").hasAttribute("inert")).toBe(false);
    expect(pane("Chords").hasAttribute("inert")).toBe(true);

    fireEvent.keyDown(screen.getByRole("tab", { name: "Face" }), { key: "ArrowRight" });
    expect(pane("Face").hasAttribute("inert")).toBe(true);
    expect(pane("Chords").hasAttribute("inert")).toBe(false);
  });

  it("comes back to the chat from the header, and is not a sheet with a backdrop", () => {
    const onClose = vi.fn();
    const { container } = renderConsole("shortcuts", { onClose });
    fireEvent.click(container.querySelector(".tabstack") as Element);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("Back to chat"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
