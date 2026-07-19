import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FOAM, WOBBLE } from "../mark/marks";
import { THEMES } from "../theme/themes";
import { SettingsView } from "./SettingsView";

function renderView(
  over: {
    themeName?: string | null;
    onPickTheme?: (name: string | null) => void;
    onPickMark?: (name: string) => void;
    onClose?: () => void;
  } = {},
) {
  return render(
    <SettingsView
      themeName={over.themeName === undefined ? null : over.themeName}
      mark={WOBBLE}
      animated={false}
      onPickTheme={over.onPickTheme ?? vi.fn()}
      onPickMark={over.onPickMark ?? vi.fn()}
      onClose={over.onClose ?? vi.fn()}
    />,
  );
}

describe("SettingsView", () => {
  it("offers Auto plus every registered theme, with Auto checked when nothing is chosen", () => {
    renderView();
    const options = screen.getAllByRole("radio", { name: /auto|midnight|daylight/iu });
    expect(options).toHaveLength(THEMES.length + 1);
    expect(screen.getByRole("radio", { name: "Auto" })).toHaveAttribute("aria-checked", "true");
  });

  it("checks the chosen theme instead of Auto once one is picked", () => {
    renderView({ themeName: "daylight" });
    expect(screen.getByRole("radio", { name: "Auto" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "daylight" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("picks a theme by name, and Auto as a null choice the toggle cannot express", () => {
    const onPickTheme = vi.fn();
    renderView({ themeName: "midnight", onPickTheme });
    fireEvent.click(screen.getByRole("radio", { name: "daylight" }));
    expect(onPickTheme).toHaveBeenCalledWith("daylight");
    fireEvent.click(screen.getByRole("radio", { name: "Auto" }));
    expect(onPickTheme).toHaveBeenCalledWith(null);
  });

  it("draws every mark style live, with the current one checked, and picks by name", () => {
    const onPickMark = vi.fn();
    const { container } = renderView({ onPickMark });
    expect(container.querySelectorAll(".seg-mark svg.mark")).toHaveLength(4);
    expect(screen.getByRole("radio", { name: "Wobble" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: "Foam" }));
    expect(onPickMark).toHaveBeenCalledWith(FOAM.name);
  });

  it("is a region of the panel with one way back, not a sheet laid over it", () => {
    const onClose = vi.fn();
    const { container } = renderView({ onClose });
    expect(screen.getByRole("region", { name: "Settings" })).toBeInTheDocument();
    // Nothing here is a backdrop, so choosing a setting cannot dismiss the view out from under
    // the user mid-comparison; leaving is the one control that says so.
    fireEvent.click(container.querySelector(".rows") as Element);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("Back to chat"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
