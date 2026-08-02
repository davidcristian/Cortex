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

/** The console wired to its own selection, which is what the panel does with it. The keyboard
 *  cannot be read off a fixed `tab` prop: selection follows focus here, so the answer to "where did
 *  the arrow leave the keyboard" is only true once the tab it asked for is the tab that is up. */
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

/** The strip, as the tab key sees it: which faces are in the page's tab order at all. */
function stops() {
  return screen
    .getAllByRole("tab")
    .filter((tab) => tab.tabIndex >= 0)
    .map((tab) => tab.textContent);
}

/** jsdom has no layout, so the two tabs are given heights: the taller keeps the one the browser
 *  measures for the shortcut list, and the other stands `spread()` px under it. Keyed off the
 *  pane's own label, so what is stubbed is the two panes and not every box in the tree. */
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
    // A tab change swaps the whole pane, so the button clicked is on its way out and about to be
    // display:none, which drops focus to the body. The arriving pane picks it up on the tab that
    // is now selected, which is also what allows the pane being left to be aria-hidden: a browser
    // refuses to hide the focused element's ancestor from assistive tech.
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Chords" }));
  });

  it("asks for a tab by name, including the one already showing (the strip cannot close it)", () => {
    const onSelectTab = vi.fn();
    renderConsole("appearance", { onSelectTab });
    fireEvent.click(screen.getByRole("tab", { name: "Chords" }));
    expect(onSelectTab).toHaveBeenCalledWith("shortcuts");
    // Idempotent by construction: showing the tab that is up is what the reducer does with this.
    fireEvent.click(screen.getByRole("tab", { name: "Face" }));
    expect(onSelectTab).toHaveBeenLastCalledWith("appearance");
  });

  it("holds one height for two close tabs, and lets the shorter go when they are not close", () => {
    let spread = TAB_SPREAD_PX;
    stubTabHeights(() => spread);
    const stack = () => document.querySelector(".tabstack") as HTMLElement;

    // At the tolerance exactly the stack still holds both, so the panel keeps the taller tab's
    // height whichever tab is up and switching tabs resizes nothing.
    const held = renderConsole("appearance");
    expect(stack().classList.contains("apart")).toBe(false);
    held.unmount();

    // One pixel further apart and the difference is a real one, so the pane not on screen leaves
    // the flow and the panel is free to morph between the two heights.
    spread = TAB_SPREAD_PX + 1;
    renderConsole("appearance");
    expect(stack().classList.contains("apart")).toBe(true);
    // The measuring pose is never left behind: it exists for one synchronous read, and outliving
    // it would hand the panel a height nothing in the stack agrees with.
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
      // The pointer has to reach the pane the face actually opens, not merely reach something: a
      // strip that names both panes and controls one of them twice is the failure to catch here.
      expect(box?.className).toContain("tabpane");
      expect(box?.getAttribute("aria-label")).toBe(label);
      expect(box?.textContent).toContain(pane === "Appearance" ? "Light" : "Switcher");
    }
  });

  it("is one stop in the tab order however many faces it has, and the stop is the one showing", () => {
    // The roving `tabindex`. Before it, both faces were stops and Tab walked the strip one face at
    // a time, which is the pattern's own counter-example: a tab list is one stop, and the arrows
    // are what move inside it.
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

    // Selection follows focus: one press both moves the keyboard and changes the view, which is
    // what the pointer's one click already did.
    fireEvent.keyDown(face, { key: "ArrowRight" });
    expect(onSelectTab).toHaveBeenLastCalledWith("shortcuts");
    expect(chords).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(chords);
    expect(stops()).toEqual(["Chords"]);

    // Off the end and round: on a strip of two this makes Right a toggle, which is the point.
    fireEvent.keyDown(chords, { key: "ArrowRight" });
    expect(document.activeElement).toBe(face);
    expect(face).toHaveAttribute("aria-selected", "true");

    // And the other way, wrapping off the front.
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
    // Pressed at the end it is already on, it asks for the tab that is up, which the reducer
    // treats as the no-op it is, and the keyboard does not move.
    fireEvent.keyDown(face, { key: "Home" });
    expect(document.activeElement).toBe(face);
  });

  it("keeps the keys it does not answer, so the panel's own chords still reach it", () => {
    const onSelectTab = vi.fn();
    renderLive("appearance", onSelectTab);
    const face = screen.getByRole("tab", { name: "Face" });
    // Ctrl and the vertical arrows cycle chats overlay-wide, so the strip must not eat them, and
    // an unanswered key must reach the window's own listener with its default intact.
    for (const key of ["ArrowDown", "ArrowUp", "Escape", "k"]) {
      expect(fireEvent.keyDown(face, { key })).toBe(true);
    }
    expect(onSelectTab).not.toHaveBeenCalled();
    // The four it does answer are claimed, because Home and End scroll the panel's clipped box
    // and the arrows scroll it sideways: movement nobody asked for, under a settled panel.
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

    // The stylesheet takes the leaving pane out too, but only after the fade, and for those 200ms
    // it was announced as hidden and still tabbable. This lands with the selection instead.
    fireEvent.keyDown(screen.getByRole("tab", { name: "Face" }), { key: "ArrowRight" });
    expect(pane("Face").hasAttribute("inert")).toBe(true);
    expect(pane("Chords").hasAttribute("inert")).toBe(false);
  });

  it("comes back to the chat from the header, and is not a sheet with a backdrop", () => {
    const onClose = vi.fn();
    const { container } = renderConsole("shortcuts", { onClose });
    // Nothing here is a backdrop, so a click meant for a control cannot dismiss the view out from
    // under the user mid-comparison; the chevron is the one control that leaves.
    fireEvent.click(container.querySelector(".tabstack") as Element);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("Back to chat"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
