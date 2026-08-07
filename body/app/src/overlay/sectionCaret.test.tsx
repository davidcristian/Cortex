import { render, screen } from "@testing-library/react";
import { useRef } from "react";
import { describe, expect, it } from "vitest";

import { useSectionCaret } from "./sectionCaret";

interface StageProps {
  readonly open: boolean;
  readonly arrival: number;
  /** Whether the section's own container is on the page at all. */
  readonly rooted?: boolean;
  readonly anchored?: boolean;
}

/**
 * A section with one control in it, an anchor outside it, and a second control outside it that
 * stands for the composer.
 *
 * The control inside stays rendered whatever `open` says, which is what a real section does: it is
 * mounted for the length of its closing roll (`Collapse`), so the caret is still on it in the commit
 * the close lands.
 */
function Stage({ open, arrival, rooted = true, anchored = true }: StageProps) {
  const section = useRef<HTMLDivElement>(null);
  const anchor = useRef<HTMLButtonElement>(null);
  const nothing = useRef<HTMLElement>(null);
  useSectionCaret(rooted ? section : nothing, anchored ? anchor : nothing, open, arrival);
  return (
    <>
      <button type="button" aria-label="anchor" ref={anchor} />
      <button type="button" aria-label="elsewhere" />
      <div ref={section}>
        <button type="button" aria-label="inside" />
      </div>
    </>
  );
}

describe("useSectionCaret", () => {
  const inside = () => screen.getByLabelText("inside");
  const anchor = () => screen.getByLabelText("anchor");

  it("hands the caret to the anchor when the section closes under it", () => {
    const { rerender } = render(<Stage open arrival={0} />);
    inside().focus();
    rerender(<Stage open={false} arrival={0} />);
    expect(document.activeElement).toBe(anchor());
  });

  it("leaves a caret that was somewhere else exactly where it was", () => {
    // The composer's case, and the whole reason the rule is guarded: Ctrl+K is a global key, so it
    // closes the list as readily from a half-typed sentence as from inside the list.
    const { rerender } = render(<Stage open arrival={0} />);
    screen.getByLabelText("elsewhere").focus();
    rerender(<Stage open={false} arrival={0} />);
    expect(document.activeElement).toBe(screen.getByLabelText("elsewhere"));
  });

  it("stands down when the section closed because a conversation arrived", () => {
    // Most of the ways the switcher closes are swap arms, and the caret belongs in the chat that
    // arrived (`Composer`). Two rules moving the caret in one commit is two events, so this one
    // defers rather than racing.
    const { rerender } = render(<Stage open arrival={4} />);
    inside().focus();
    rerender(<Stage open={false} arrival={5} />);
    expect(document.activeElement).toBe(inside());
  });

  it("touches nothing while the section is opening or standing open", () => {
    const { rerender } = render(<Stage open={false} arrival={0} />);
    inside().focus();
    rerender(<Stage open arrival={0} />);
    expect(document.activeElement).toBe(inside());
    // And a render that changes something else about an open section is not a close either.
    rerender(<Stage open arrival={1} />);
    expect(document.activeElement).toBe(inside());
  });

  it("does nothing when it has no section to look inside", () => {
    const { rerender } = render(<Stage open arrival={0} rooted={false} />);
    inside().focus();
    rerender(<Stage open={false} arrival={0} rooted={false} />);
    expect(document.activeElement).toBe(inside());
  });

  it("does nothing when it has no anchor to hand the caret to", () => {
    const { rerender } = render(<Stage open arrival={0} anchored={false} />);
    inside().focus();
    rerender(<Stage open={false} arrival={0} anchored={false} />);
    expect(document.activeElement).toBe(inside());
  });
});
