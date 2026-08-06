import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "./Composer";

const field = () => screen.getByLabelText("Message") as HTMLTextAreaElement;
const pill = () => field().parentElement as HTMLDivElement;

/** jsdom has no layout, so the field is given the two numbers the effect reads. `clientHeight` is
 *  what a `rows={1}` textarea measures at `height: auto` (one line); `scrollHeight` is what the
 *  content needs, and it is a function of the LAYOUT so a test can pose the real question: the two
 *  widths disagree, so which one did the component ask? */
function fakeMetrics(oneLine: number, needs: (stacked: boolean) => number) {
  Object.defineProperty(field(), "clientHeight", { configurable: true, value: oneLine });
  Object.defineProperty(field(), "scrollHeight", {
    configurable: true,
    get(this: HTMLTextAreaElement) {
      return needs((this.parentElement as HTMLElement).classList.contains("stacked"));
    },
  });
  // The pill follows its field, plus the button's own row once the layout stacks. The chrome is
  // approximated (the shape is what the component reads, not the exact padding), but the two ways
  // it can change are the real ones, which is what makes "did it actually resize?" a real question.
  Object.defineProperty(pill(), "offsetHeight", {
    configurable: true,
    get(this: HTMLElement) {
      const grown = parseInt(field().style.height || "0", 10);
      return grown + (this.classList.contains("stacked") ? 40 : 0);
    },
  });
}

describe("Composer", () => {
  it("sends on Enter and clears, but Shift+Enter and other keys do not", () => {
    const onSubmit = vi.fn();
    render(<Composer busy={false} arrival={null} onSubmit={onSubmit} onStop={vi.fn()} onResize={vi.fn()} />);
    fireEvent.change(field(), { target: { value: "hello" } });
    fireEvent.keyDown(field(), { key: "Enter", shiftKey: true });
    fireEvent.keyDown(field(), { key: "a" });
    expect(onSubmit).not.toHaveBeenCalled();
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledWith("hello");
    expect(field().value).toBe("");
  });

  it("sends on the send button and lights it only with text", () => {
    const onSubmit = vi.fn();
    render(<Composer busy={false} arrival={null} onSubmit={onSubmit} onStop={vi.fn()} onResize={vi.fn()} />);
    expect(screen.getByLabelText("Send").className).not.toContain("live");
    fireEvent.change(field(), { target: { value: "hi" } });
    expect(screen.getByLabelText("Send").className).toContain("live");
    fireEvent.click(screen.getByLabelText("Send"));
    expect(onSubmit).toHaveBeenCalledWith("hi");
  });

  it("becomes a stop button while busy: it cancels the turn and never submits", () => {
    const onSubmit = vi.fn();
    const onStop = vi.fn();
    render(<Composer busy={true} arrival={null} onSubmit={onSubmit} onStop={onStop} onResize={vi.fn()} />);
    fireEvent.change(field(), { target: { value: "x" } });
    const stop = screen.getByLabelText("Stop");
    expect(stop.className).not.toContain("live");
    expect(stop.className).toContain("stopping");
    fireEvent.click(stop);
    expect(onStop).toHaveBeenCalledOnce();
    // Enter still routes to submit, but the busy guard keeps it from firing mid-turn.
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("takes focus when the panel opens (focus-on-summon), and scrolls nothing to do it", () => {
    const focus = vi.spyOn(HTMLTextAreaElement.prototype, "focus");
    const { rerender } = render(
      <Composer busy={false} arrival={null} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />,
    );
    expect(document.activeElement).not.toBe(field());
    rerender(<Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />);
    expect(document.activeElement).toBe(field());
    // The panel clips its overflow, which makes it a scroll box the user can never scroll and the
    // ENGINE can, and bringing a newly focused element into view is when it does. Coming back from
    // the console this field is below the panel's clipped edge for the length of the ease, so the
    // panel was scrolled to reach it and every row in the window lurched up: `panel.scrollTop` went
    // 0 to 139 in the frame focus landed, traced at 640x720 with the session list open.
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    focus.mockRestore();
  });

  it("takes focus again when another conversation arrives, but not on any other render", () => {
    const composer = (arrival: number | null) => (
      <Composer busy={false} arrival={arrival} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />
    );
    const { rerender } = render(composer(3));
    expect(document.activeElement).toBe(field());
    // A reader who has gone somewhere else in the panel keeps their place: a stream re-rendering
    // the chat around a still draft must not reach in and take the caret back.
    (document.activeElement as HTMLElement).blur();
    rerender(composer(3));
    expect(document.activeElement).not.toBe(field());
    // A chat arriving is the case that moves it. The gestures that fire one are made inside
    // sections the swap takes away (a switcher row, a reminder's open control, a delete confirm),
    // so without this the control pressed stops existing and focus falls to `<body>`.
    rerender(composer(4));
    expect(document.activeElement).toBe(field());
    // And a chat arriving while the console is over the chat, or the panel is shut, is not a
    // landing at all: there is nothing on screen here to put a caret in.
    (document.activeElement as HTMLElement).blur();
    rerender(composer(null));
    rerender(composer(null));
    expect(document.activeElement).not.toBe(field());
  });

  it("auto-grows with its content up to the cap, then holds and scrolls", () => {
    render(<Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />);
    fakeMetrics(34, () => 64);
    fireEvent.change(field(), { target: { value: "two\nlines" } });
    expect(field().style.height).toBe("64px");
    fakeMetrics(34, () => 400);
    fireEvent.change(field(), { target: { value: "far\ntoo\nmany\nlines\nnow\nreally" } });
    expect(field().style.height).toBe("120px");
  });

  it("keeps the button beside the field on one line and drops it below once it wraps", () => {
    render(<Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />);
    fakeMetrics(34, () => 34);
    fireEvent.change(field(), { target: { value: "one line" } });
    expect(pill().className).toBe("composer");
    fakeMetrics(34, () => 50);
    fireEvent.change(field(), { target: { value: "one line\nand a second" } });
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("50px");
  });

  it("decides the layout at the inline width, so a draft in the band cannot flip-flop", () => {
    render(<Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />);
    // The band: this draft needs two lines while the button holds its column beside the field, and
    // one once the button drops below and hands the width back. Asked at the width in use, the two
    // layouts would answer each other forever.
    fakeMetrics(34, (stacked) => (stacked ? 34 : 50));
    fireEvent.change(field(), { target: { value: "a draft that only just wraps" } });
    expect(pill().className).toBe("composer stacked");
    // Sized for the layout it chose (one line at the full width), not for the one it asked at.
    expect(field().style.height).toBe("34px");
    // Still stacked a keystroke later: the answer is the text's, not the current layout's.
    fireEvent.change(field(), { target: { value: "a draft that only just wraps!" } });
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("34px");
  });

  it("pins the pill's floor for the measurement and hands it back afterwards", () => {
    render(<Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />);
    fakeMetrics(34, () => 34);
    fireEvent.change(field(), { target: { value: "one line" } });
    // The measurement collapses the field and takes the layout class off, and at the panel's
    // ceiling that lets the pill shrink to its smaller automatic minimum while the log above grows
    // into the gap, which costs the log its scroll position permanently. jsdom has no layout to
    // catch that with, but it can ask the question the browser answers with pixels: at the instant
    // the field is measured, is the pill still standing on the height it walked in with?
    const floors: string[] = [];
    Object.defineProperty(field(), "scrollHeight", {
      configurable: true,
      get() {
        floors.push(pill().style.minHeight);
        return 50;
      },
    });
    fireEvent.change(field(), { target: { value: "one line\nand a second" } });
    expect(floors).toEqual(["34px", "34px"]);
    // And it is only a floor for the measurement: the pill sizes itself again on the way out.
    expect(pill().style.minHeight).toBe("");
  });

  it("tells the container when the pill resizes, and stays quiet when it only retypes", () => {
    const onResize = vi.fn();
    render(<Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={onResize} />);
    // A draft inside one line: the pill is the same size it was, so nothing is announced. This is
    // the case that must stay silent, since every keystroke of a short message passes through here.
    fakeMetrics(34, () => 34);
    fireEvent.change(field(), { target: { value: "one line" } });
    onResize.mockClear();
    fireEvent.change(field(), { target: { value: "one line still" } });
    expect(onResize).not.toHaveBeenCalled();
    // Restacking is a resize (the button takes a row of its own), and so is a further line after
    // it. The log above uses this to hold its tail, which the pill is now covering more of.
    fakeMetrics(34, () => 50);
    fireEvent.change(field(), { target: { value: "one line\nand a second" } });
    expect(onResize).toHaveBeenCalledOnce();
    fakeMetrics(34, () => 66);
    fireEvent.change(field(), { target: { value: "one line\nand a second\nand a third" } });
    expect(onResize).toHaveBeenCalledTimes(2);
  });

  it("re-measures when the viewport resizes, since the answer belongs to a width", () => {
    const onResize = vi.fn();
    render(<Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={onResize} />);
    // A draft that fits one line at the width it was typed at.
    let narrow = false;
    fakeMetrics(34, () => (narrow ? 50 : 34));
    fireEvent.change(field(), { target: { value: "a draft that fits one line at the wide panel" } });
    expect(pill().className).toBe("composer");
    expect(field().style.height).toBe("34px");
    onResize.mockClear();
    // The panel narrows under a standing draft: the same text now wraps, and nothing was typed. The
    // keystroke that used to be the only trigger would have left the field scrolled inside a box
    // sized for a line that no longer fits, with the button still holding its column beside it.
    narrow = true;
    fireEvent(window, new Event("resize"));
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("50px");
    // And the pill really did change size, so the log above hears about it exactly as it does for a
    // keystroke that grows the pill.
    expect(onResize).toHaveBeenCalledOnce();
  });

  it("stops listening for resizes once it is gone", () => {
    const { unmount } = render(
      <Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />,
    );
    // The measurement reads and writes the two nodes this component owns, and React nulls those refs
    // on the way out, so a listener left behind does not merely waste a frame: the first resize after
    // the panel is gone throws on a null field. Left unremoved, this test catches exactly that
    // (`TypeError: Cannot read properties of null (reading 'style')`, surfaced as a window error).
    const errors: string[] = [];
    const onError = (event: ErrorEvent) => errors.push(String(event.error));
    window.addEventListener("error", onError);
    unmount();
    fireEvent(window, new Event("resize"));
    window.removeEventListener("error", onError);
    expect(errors).toEqual([]);
  });

  it("returns to one row when the draft is sent", () => {
    render(<Composer busy={false} arrival={0} onSubmit={vi.fn()} onStop={vi.fn()} onResize={vi.fn()} />);
    fakeMetrics(34, (stacked) => (field().value === "" ? 34 : stacked ? 50 : 66));
    fireEvent.change(field(), { target: { value: "a draft\nover two lines" } });
    expect(pill().className).toBe("composer stacked");
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(pill().className).toBe("composer");
    expect(field().style.height).toBe("34px");
  });
});
