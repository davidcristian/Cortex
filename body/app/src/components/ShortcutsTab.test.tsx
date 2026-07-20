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
    for (const group of ["Writing", "Chats", "The window"]) {
      expect(screen.getByText(group)).toBeInTheDocument();
    }
    for (const label of [
      "Send",
      "Newline",
      "New chat",
      "Previous chat",
      "Next chat",
      "Chat switcher",
      "Summon or focus",
      "This list",
      "Close the console",
      "Dismiss",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // The hint strip beside the composer carries four of these; this is the complete list, so a
    // binding that is only ever written down here must actually be written down here.
    expect(screen.getByText("to the orb mid-turn")).toBeInTheDocument();
  });

  it("is a wall of cards, the same object as the appearance tab beside it", () => {
    const { container } = render(<ShortcutsTab />);
    // Ten bindings, ten tiles, and no hairline-separated rows left over: a list of full-width
    // rules next to a grid of swatches read as two different screens.
    expect(container.querySelectorAll(".skey")).toHaveLength(10);
    expect(container.querySelectorAll(".row")).toHaveLength(0);
    // The two whose keys will not fit beside their label at half width span the grid instead.
    expect(card("Summon or focus").className).toContain("wide");
    expect(card("Dismiss").className).toContain("wide");
    expect(card("Send").className).not.toContain("wide");
  });

  it("gives every key its own cap, so a chord reads as the keys it is", () => {
    render(<ShortcutsTab />);
    const caps = [...card("New chat").querySelectorAll("b")].map((cap) => cap.textContent);
    expect(caps).toEqual(["Ctrl", "N"]);
    expect([...card("Summon or focus").querySelectorAll("b")].map((c) => c.textContent)).toEqual([
      "Ctrl",
      "Alt",
      "Space",
    ]);
    // Modifier and key are separate caps even when both are drawn glyphs.
    expect(card("Newline").querySelectorAll("b")).toHaveLength(2);
    expect(card("Previous chat").querySelectorAll("b")).toHaveLength(2);
  });

  it("draws a non-letter key with the header's outline icon, never a Unicode symbol", () => {
    render(<ShortcutsTab />);
    for (const label of ["Send", "Newline", "Previous chat"]) {
      for (const cap of card(label).querySelectorAll("b.key")) {
        // One glyph per cap, and it is an SVG from `icons.tsx` rather than a character.
        expect(cap.querySelectorAll("svg")).toHaveLength(1);
        expect(cap.textContent).toBe("");
      }
    }
    expect(card("Send").querySelectorAll("b.key")).toHaveLength(1);
    expect(card("Newline").querySelectorAll("b.key")).toHaveLength(2);
  });

  it("says Esc leaves the console before it dismisses the panel, in that order", () => {
    render(<ShortcutsTab />);
    const labels = [...document.querySelectorAll(".skey-label")].map(
      (label) => label.firstChild?.textContent,
    );
    expect(labels.indexOf("Close the console")).toBeLessThan(labels.indexOf("Dismiss"));
    expect(card("Close the console").querySelector("b")?.textContent).toBe("Esc");
    expect(card("Dismiss").querySelector("b")?.textContent).toBe("Esc");
  });
});
