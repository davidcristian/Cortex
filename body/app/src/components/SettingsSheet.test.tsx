import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FOAM, WOBBLE } from "../mark/marks";
import { THEMES } from "../theme/themes";
import { SettingsSheet } from "./SettingsSheet";

function renderSheet(
  over: {
    themeName?: string | null;
    onPickTheme?: (name: string | null) => void;
    onPickMark?: (name: string) => void;
    onClose?: () => void;
  } = {},
) {
  return render(
    <SettingsSheet
      themeName={over.themeName === undefined ? null : over.themeName}
      mark={WOBBLE}
      animated={false}
      onPickTheme={over.onPickTheme ?? vi.fn()}
      onPickMark={over.onPickMark ?? vi.fn()}
      onClose={over.onClose ?? vi.fn()}
    />,
  );
}

describe("SettingsSheet", () => {
  it("offers Auto plus every registered theme, with Auto checked when nothing is chosen", () => {
    renderSheet();
    const options = screen.getAllByRole("radio", { name: /auto|midnight|daylight/iu });
    expect(options).toHaveLength(THEMES.length + 1);
    expect(screen.getByRole("radio", { name: "Auto" })).toHaveAttribute("aria-checked", "true");
  });

  it("checks the chosen theme instead of Auto once one is picked", () => {
    renderSheet({ themeName: "daylight" });
    expect(screen.getByRole("radio", { name: "Auto" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "daylight" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("picks a theme by name, and Auto as a null choice the toggle cannot express", () => {
    const onPickTheme = vi.fn();
    renderSheet({ themeName: "midnight", onPickTheme });
    fireEvent.click(screen.getByRole("radio", { name: "daylight" }));
    expect(onPickTheme).toHaveBeenCalledWith("daylight");
    fireEvent.click(screen.getByRole("radio", { name: "Auto" }));
    expect(onPickTheme).toHaveBeenCalledWith(null);
  });

  it("draws every mark style live, with the current one checked, and picks by name", () => {
    const onPickMark = vi.fn();
    const { container } = renderSheet({ onPickMark });
    expect(container.querySelectorAll(".markopt svg.mark")).toHaveLength(4);
    expect(screen.getByRole("radio", { name: /Wobble/u })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: /Foam/u }));
    expect(onPickMark).toHaveBeenCalledWith(FOAM.name);
  });

  it("closes on a click outside its card, but a click on the card itself never closes it", () => {
    const onClose = vi.fn();
    const { container } = renderSheet({ onClose });
    fireEvent.click(screen.getByRole("dialog", { name: "Settings" }));
    expect(onClose).toHaveBeenCalledOnce();
    // Choosing a setting must not dismiss the sheet under the user mid-comparison.
    const card = container.querySelector(".set-card");
    expect(card).not.toBeNull();
    fireEvent.click(card as Element);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
