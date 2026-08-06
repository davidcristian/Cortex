import { fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { describe, expect, it } from "vitest";

import { caretKey, heir, useRowCaret } from "./rowCaret";

describe("caretKey", () => {
  it("names one control in one row, and passes a missing row straight through", () => {
    expect(caretKey("delete", "c1")).toBe("delete:c1");
    // What `heir` answers for a list with nothing left, so the call sites stay one expression.
    expect(caretKey("delete", null)).toBeNull();
  });
});

describe("heir", () => {
  it("gives a departing row's place to the row below it", () => {
    expect(heir(["a", "b", "c"], "b")).toBe("c");
  });

  it("gives it to the row above when the one leaving was last", () => {
    expect(heir(["a", "b"], "b")).toBe("a");
  });

  it("gives it to nobody when the row leaving was the only one", () => {
    expect(heir(["a"], "a")).toBeNull();
    expect(heir([], "a")).toBeNull();
  });

  it("gives it to nobody for a row that is not in the list, having no place to leave", () => {
    // Not reachable from either list, both of which ask about a row they are rendering, and the
    // answer that stays right if one ever asks about a row that has already gone: the row after
    // "not found" is not the first row.
    expect(heir(["a", "b"], "gone")).toBeNull();
  });
});

interface StageProps {
  readonly send: string | null;
  /** Whether the list's own container is on the page at all. */
  readonly rooted?: boolean;
  readonly anchored?: boolean;
}

/** A list of two named controls plus an anchor outside it, driven the way the two real lists drive
 *  it: a gesture names the control the caret should be in once the change is on screen. */
function Stage({ send, rooted = true, anchored = true }: StageProps) {
  const list = useRef<HTMLUListElement>(null);
  const anchor = useRef<HTMLButtonElement>(null);
  const nothing = useRef<HTMLElement>(null);
  const caret = useRowCaret(rooted ? list : nothing, anchored ? anchor : nothing);
  return (
    <>
      <button type="button" aria-label="anchor" ref={anchor} />
      <button type="button" aria-label="fire" onClick={() => caret(send)} />
      <ul ref={list}>
        <li>
          <button type="button" data-caret="delete:a" aria-label="delete a" />
        </li>
        <li>
          <input data-caret="name:b" aria-label="name b" defaultValue="Second" />
        </li>
      </ul>
    </>
  );
}

describe("useRowCaret", () => {
  const fire = (): void => void fireEvent.click(screen.getByLabelText("fire"));

  it("moves the caret to the named control in the commit that reshapes the list", () => {
    render(<Stage send="delete:a" />);
    expect(document.activeElement).toBe(document.body);
    fire();
    expect(document.activeElement).toBe(screen.getByLabelText("delete a"));
  });

  it("selects a field it lands in, a list only sending the caret into one to replace it", () => {
    render(<Stage send="name:b" />);
    fire();
    const input = screen.getByLabelText<HTMLInputElement>("name b");
    expect(document.activeElement).toBe(input);
    expect([input.selectionStart, input.selectionEnd]).toEqual([0, "Second".length]);
  });

  it("falls back to the anchor when nothing claims the name, which is an emptied list", () => {
    const { rerender } = render(<Stage send={null} />);
    fire();
    expect(document.activeElement).toBe(screen.getByLabelText("anchor"));
    // A name no row carries is the same case: there is nothing in the list to hand it to.
    screen.getByLabelText("delete a").focus();
    rerender(<Stage send="delete:gone" />);
    fire();
    expect(document.activeElement).toBe(screen.getByLabelText("anchor"));
  });

  it("touches nothing on the renders no gesture asked about, which is nearly all of them", () => {
    // A stream re-rendering the chat around an untouched list must not reach in and take the caret
    // off whatever the reader moved it to.
    const { rerender } = render(<Stage send="delete:a" />);
    screen.getByLabelText("anchor").focus();
    rerender(<Stage send="delete:a" />);
    expect(document.activeElement).toBe(screen.getByLabelText("anchor"));
  });

  it("does nothing at all when it has neither a list to look in nor an anchor to fall back on", () => {
    render(<Stage send="delete:a" rooted={false} anchored={false} />);
    fire();
    expect(document.activeElement).toBe(document.body);
  });
});
