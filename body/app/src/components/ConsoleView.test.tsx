import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WOBBLE } from "../mark/marks";
import { CONSOLE_TABS, type ConsoleTab } from "../overlay/overlayState";
import { ConsoleView } from "./ConsoleView";

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

describe("ConsoleView", () => {
  it("is one region with a strip of every tab, the showing one selected", () => {
    renderConsole("appearance");
    expect(screen.getByRole("region", { name: "Console" })).toBeInTheDocument();
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
    expect(screen.getByRole("radiogroup", { name: "Mark style" })).toBeInTheDocument();
    expect(screen.queryByText("Chat switcher")).toBeNull();
    unmount();
    renderConsole("shortcuts");
    expect(screen.getByRole("tabpanel", { name: "Shortcuts" })).toBeInTheDocument();
    expect(screen.getByText("Switcher")).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: "Mark style" })).toBeNull();
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

  it("comes back to the chat from the header, and is not a sheet with a backdrop", () => {
    const onClose = vi.fn();
    const { container } = renderConsole("shortcuts", { onClose });
    // Nothing here is a backdrop, so a click meant for a control cannot dismiss the view out from
    // under the user mid-comparison; the chevron is the one control that leaves.
    fireEvent.click(container.querySelector(".tabpanel") as Element);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("Back to chat"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
