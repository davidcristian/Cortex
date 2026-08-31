import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ShortcutsTab } from "./ShortcutsTab";

/** The card holding `label`, as the DOM sees it: the label's own tile. */
function card(label: string): HTMLElement {
  return screen.getByText(label).closest(".skey") as HTMLElement;
}

describe("ShortcutsTab", () => {
  it("lists every binding, grouped by what it is for", () => {
    render(<ShortcutsTab />);
    for (const group of ["Ink", "Chats", "The window"]) {
      expect(screen.getByText(group)).toBeInTheDocument();
    }
    for (const label of [
      "Send",
      "New line",
      "New",
      "Previous",
      "Next",
      "Switcher",
      "Summon",
      "This tab",
      "Dismiss",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("is a wall of cards, the same object as the appearance tab beside it", () => {
    const { container } = render(<ShortcutsTab />);
    expect(container.querySelectorAll(".skey")).toHaveLength(9);
    expect(container.querySelectorAll(".row")).toHaveLength(0);
    const wide = [...container.querySelectorAll(".skey")].filter((t) =>
      t.className.includes("wide"),
    );
    expect(wide).toHaveLength(1);
    expect(card("Summon").className).toContain("wide");
  });

  it("gives every key its own cap, so a chord reads as the keys it is", () => {
    render(<ShortcutsTab />);
    const caps = [...card("New").querySelectorAll("b")].map((cap) => cap.textContent);
    expect(caps).toEqual(["Ctrl", "N"]);
    expect([...card("Summon").querySelectorAll("b")].map((c) => c.textContent)).toEqual([
      "Ctrl",
      "Alt",
      "Space",
    ]);
    expect(card("New line").querySelectorAll("b")).toHaveLength(2);
    expect(card("Previous").querySelectorAll("b")).toHaveLength(2);
  });

  it("draws a non-letter key with the header's outline icon, never a Unicode symbol", () => {
    render(<ShortcutsTab />);
    for (const label of ["Send", "New line", "Previous"]) {
      for (const cap of card(label).querySelectorAll("b.key")) {
        expect(cap.querySelectorAll("svg")).toHaveLength(1);
        expect(cap.textContent).toBe("");
      }
    }
    expect(card("Send").querySelectorAll("b.key")).toHaveLength(1);
    expect(card("New line").querySelectorAll("b.key")).toHaveLength(1);
    expect(card("New line").querySelector("b")?.textContent).toBe("Shift");
  });

  it("gives Esc one card, not one per thing it backs out of", () => {
    const { container } = render(<ShortcutsTab />);
    const escs = [...container.querySelectorAll(".skey")].filter((tile) =>
      [...tile.querySelectorAll("b")].some((cap) => cap.textContent === "Esc"),
    );
    expect(escs).toHaveLength(1);
    expect(card("Dismiss").querySelector("b")?.textContent).toBe("Esc");
  });
});
