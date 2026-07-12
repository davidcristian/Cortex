import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ShortcutSheet } from "./ShortcutSheet";

describe("ShortcutSheet", () => {
  it("lists the full shortcut set and closes on a click anywhere", () => {
    const onClose = vi.fn();
    render(<ShortcutSheet onClose={onClose} />);
    const sheet = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
    for (const label of [
      "Summon or focus",
      "Send",
      "Newline",
      "Dismiss (orb while working)",
      "New chat",
      "Previous / next chat",
      "Chat switcher",
      "This sheet",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    fireEvent.click(sheet);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
