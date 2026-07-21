import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EDGES, LUCID, TRANCE as TRANCE_EDGE } from "../edge/edges";
import { MARKS, TANGENT, MULL } from "../mark/marks";
import { THEMES, resolveTheme } from "../theme/themes";
import { AppearanceTab } from "./AppearanceTab";

/** A token as the DOM will store it: the engine normalises `#0C0A12` to `rgb(12, 10, 18)` on the
 *  way into a style, so a registry value has to make the same trip before it is compared. */
function asStyled(value: string): string {
  const probe = document.createElement("span");
  probe.style.background = value;
  return probe.style.background;
}

function renderTab(
  over: {
    themeName?: string | null;
    onPickTheme?: (name: string | null) => void;
    onPickMark?: (name: string) => void;
    onPickEdge?: (name: string) => void;
  } = {},
) {
  return render(
    <AppearanceTab
      themeName={over.themeName === undefined ? null : over.themeName}
      mark={MULL}
      edge={LUCID}
      animated={false}
      onPickTheme={over.onPickTheme ?? vi.fn()}
      onPickMark={over.onPickMark ?? vi.fn()}
      onPickEdge={over.onPickEdge ?? vi.fn()}
    />,
  );
}

describe("AppearanceTab", () => {
  it("offers Auto plus every registered theme, with Auto checked when nothing is chosen", () => {
    renderTab();
    const tiles = screen.getByRole("radiogroup", { name: "Theme" });
    // A map over the registry, so a fifth theme appears here with no change to this view.
    expect(tiles.querySelectorAll(".tile")).toHaveLength(THEMES.length + 1);
    expect(screen.getByRole("radio", { name: "Auto" })).toHaveAttribute("aria-checked", "true");
  });

  it("draws each theme as a miniature panel in that theme's own colours", () => {
    const { container } = renderTab();
    const minis = container.querySelectorAll(".tiles .mini");
    // One per theme, plus the two halves of the Auto tile's diagonal split.
    expect(minis).toHaveLength(THEMES.length + 2);
    for (const theme of THEMES) {
      const tile = screen.getByRole("radio", { name: theme.name });
      const mini = tile.querySelector(".mini") as HTMLElement;
      expect(mini.style.background).not.toBe("");
      // The colours come from the registry, never re-typed here: a theme that changed its ground
      // would change this preview, and a preview that stopped matching would fail.
      expect(mini.style.background).toBe(asStyled(theme.tokens.bg));
      expect((mini.querySelector(".mini-title") as HTMLElement).style.background).toBe(
        asStyled(theme.tokens.text),
      );
    }
  });

  it("splits the Auto tile between exactly the two themes Auto can resolve to", () => {
    renderTab();
    const auto = screen.getByRole("radio", { name: "Auto" });
    const [dark, light] = auto.querySelectorAll(".mini");
    // Asked of the resolver, not named: Auto follows the system, and the system is one of two.
    expect((dark as HTMLElement).style.background).toBe(
      asStyled(resolveTheme(null, true).tokens.bg),
    );
    expect((light as HTMLElement).style.background).toBe(
      asStyled(resolveTheme(null, false).tokens.bg),
    );
    expect(auto.querySelector(".mini-half")?.contains(light as Node)).toBe(true);
  });

  it("checks the chosen theme instead of Auto once one is picked, and picks by name", () => {
    const onPickTheme = vi.fn();
    renderTab({ themeName: "midnight", onPickTheme });
    expect(screen.getByRole("radio", { name: "Auto" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "midnight" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    fireEvent.click(screen.getByRole("radio", { name: "daylight" }));
    expect(onPickTheme).toHaveBeenCalledWith("daylight");
    // Auto is the one choice the header's toggle cannot express, so it is a null pick.
    fireEvent.click(screen.getByRole("radio", { name: "Auto" }));
    expect(onPickTheme).toHaveBeenCalledWith(null);
  });

  it("draws every mark style as its own real bubble, big enough to tell apart by watching", () => {
    const onPickMark = vi.fn();
    const { container } = renderTab({ onPickMark });
    const marks = container.querySelectorAll(".tile svg.mark");
    expect(marks).toHaveLength(MARKS.length);
    // Four real marks, not four copies of one: the outlines are what differ between the styles,
    // so the drawn geometry has to differ too (a shared component with the same data would not).
    const outlines = new Set(
      [...marks].map((mark) => mark.querySelector(".mark-rim")?.getAttribute("d")),
    );
    expect(outlines.size).toBe(MARKS.length);
    expect([...marks].every((mark) => mark.getAttribute("width") === "40")).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: "Tangent" }));
    expect(onPickMark).toHaveBeenCalledWith(TANGENT.name);
  });

  it("says what the chosen mark does, under the row it was chosen from", () => {
    renderTab();
    expect(screen.getByRole("radio", { name: "Mull" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText(MULL.note)).toBeInTheDocument();
  });

  it("offers the window ladder from the registry, in the registry's own order", () => {
    renderTab();
    const group = screen.getByRole("radiogroup", { name: "Window" });
    // The order is the explanation, Still to Trance, and it comes from the registry: a fifth
    // edge appears here, in its place on the ladder, with no change to this view.
    expect([...group.querySelectorAll(".tile-name")].map((name) => name.textContent)).toEqual(
      EDGES.map((edge) => edge.label),
    );
    expect(group.querySelectorAll("svg.edge-mini")).toHaveLength(EDGES.length);
  });

  it("checks the chosen edge and says what it does, under the row it was chosen from", () => {
    renderTab();
    expect(screen.getByRole("radio", { name: "Lucid" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText(LUCID.note)).toBeInTheDocument();
  });

  it("picks an edge by its stored name", () => {
    const onPickEdge = vi.fn();
    renderTab({ onPickEdge });
    fireEvent.click(screen.getByRole("radio", { name: "Trance" }));
    expect(onPickEdge).toHaveBeenCalledWith(TRANCE_EDGE.name);
  });
});
