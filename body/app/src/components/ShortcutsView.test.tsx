import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ShortcutsView } from "./ShortcutsView";

describe("ShortcutsView", () => {
  it("lists the full shortcut set and comes back to the chat", () => {
    const onClose = vi.fn();
    render(<ShortcutsView onClose={onClose} />);
    expect(screen.getByRole("region", { name: "Shortcuts" })).toBeInTheDocument();
    for (const label of [
      "Summon or focus",
      "Send",
      "Newline",
      "Dismiss",
      "New chat",
      "Previous / next chat",
      "Chat switcher",
      "This view",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // The hint strip beside the composer carries four of these; this is the complete list, so a
    // binding that is only ever written down here must actually be written down here.
    expect(screen.getByText("to the orb while a turn is running")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Back to chat"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
