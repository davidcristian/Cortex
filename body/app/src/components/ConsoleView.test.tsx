import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WOBBLE } from "../mark/marks";
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
      mark={WOBBLE}
      animated={false}
      onPickTheme={vi.fn()}
      onPickMark={vi.fn()}
      onSelectTab={over.onSelectTab ?? vi.fn()}
      onClose={over.onClose ?? vi.fn()}
    />,
  );
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
    return this.getAttribute("aria-label") === "Appearance" ? 290 - spread() : 290;
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
    expect(screen.getByRole("tab", { name: "Appearance" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Shortcuts" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("shows the appearance choices on one tab and the shortcut list on the other", () => {
    const { unmount } = renderConsole("appearance");
    expect(screen.getByRole("tabpanel", { name: "Appearance" })).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "Iris" })).toBeInTheDocument();
    expect(screen.queryByText("Chat switcher")).toBeNull();
    unmount();
    renderConsole("shortcuts");
    expect(screen.getByRole("tabpanel", { name: "Shortcuts" })).toBeInTheDocument();
    expect(screen.getByText("Switcher")).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: "Iris" })).toBeNull();
  });

  it("takes focus onto the tab it is showing, since the strip it was clicked on is leaving", () => {
    renderConsole("shortcuts");
    // A tab change swaps the whole pane, so the button clicked is on its way out and about to be
    // display:none, which drops focus to the body. The arriving pane picks it up on the tab that
    // is now selected, which is also what allows the pane being left to be aria-hidden: a browser
    // refuses to hide the focused element's ancestor from assistive tech.
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Shortcuts" }));
  });

  it("asks for a tab by name, including the one already showing (the strip cannot close it)", () => {
    const onSelectTab = vi.fn();
    renderConsole("appearance", { onSelectTab });
    fireEvent.click(screen.getByRole("tab", { name: "Shortcuts" }));
    expect(onSelectTab).toHaveBeenCalledWith("shortcuts");
    // Idempotent by construction: showing the tab that is up is what the reducer does with this.
    fireEvent.click(screen.getByRole("tab", { name: "Appearance" }));
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
