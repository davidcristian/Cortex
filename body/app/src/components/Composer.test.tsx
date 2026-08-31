import { fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { draftOf, dropDraft, parkDraft } from "../overlay/drafts";
import { Composer } from "./Composer";

const field = () => screen.getByLabelText("Message") as HTMLTextAreaElement;
const pill = () => field().parentElement as HTMLDivElement;

interface StageProps {
  readonly sessionId?: string;
  readonly busy?: boolean;
  readonly arrival?: number | null;
  readonly seed?: Record<string, string>;
  readonly onSubmit?: (text: string) => void;
  readonly onStop?: () => void;
  readonly onResize?: () => void;
}

/**
 * The composer holds no text of its own, so a test that types needs the state that does. This is a
 * small version of the reducer's draft half, running its real rules (`overlay/drafts.ts`,
 * `turnState.submit`): a keystroke is parked under the chat on screen, and a send empties the field
 * that held what was sent and leaves any other text alone. It calls the real functions rather than
 * restating them, so a change to them changes this too.
 *
 * A swap is a re-render with another `sessionId`, as it is in production, which lets these tests
 * ask whether the field shows the conversation's own sentence or the last one typed anywhere.
 */
function Stage({
  sessionId = "a",
  busy = false,
  arrival = null,
  seed = {},
  onSubmit = () => undefined,
  onStop = () => undefined,
  onResize = () => undefined,
}: StageProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>(seed);
  // The field's ref belongs to the view above in production, so that the reminder stack can hand
  // the caret back to the conversation when its last row goes (`ChatView`, `overlay/rowCaret.ts`).
  const field = useRef<HTMLTextAreaElement>(null!);
  return (
    <Composer
      field={field}
      busy={busy}
      draft={draftOf(drafts, sessionId)}
      arrival={arrival}
      onSubmit={(text) => {
        onSubmit(text);
        if (text.trim().length > 0) {
          setDrafts((held) => (draftOf(held, sessionId) === text ? dropDraft(held, sessionId) : held));
        }
      }}
      onDraft={(text) => setDrafts((held) => parkDraft(held, sessionId, text))}
      onStop={onStop}
      onResize={onResize}
    />
  );
}

/** jsdom has no layout, so the field is given the two numbers the effect reads. `clientHeight` is
 *  what a `rows={1}` textarea measures at `height: auto` (one line); `scrollHeight` is what the
 *  content needs, and it is computed from the layout so that a test can give the two widths
 *  different answers and see which one the component measured at. */
function fakeMetrics(oneLine: number, needs: (stacked: boolean) => number) {
  Object.defineProperty(field(), "clientHeight", { configurable: true, value: oneLine });
  Object.defineProperty(field(), "scrollHeight", {
    configurable: true,
    get(this: HTMLTextAreaElement) {
      return needs((this.parentElement as HTMLElement).classList.contains("stacked"));
    },
  });
  // The pill follows its field, plus the button's own row once the layout stacks. The padding is
  // approximated, since the component reads the shape rather than exact pixels, but the two ways
  // the height can change are the real ones, so a resize here is a resize in the browser too.
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
    render(<Stage onSubmit={onSubmit} />);
    fireEvent.change(field(), { target: { value: "hello" } });
    fireEvent.keyDown(field(), { key: "Enter", shiftKey: true });
    fireEvent.keyDown(field(), { key: "a" });
    expect(onSubmit).not.toHaveBeenCalled();
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledWith("hello");
    expect(field().value).toBe("");
  });

  it("shows the arriving conversation's own sentence, never the one it replaced", () => {
    // The defect this covers, at the component: the field was never unmounted and held one text for
    // the whole overlay, so "half a question" typed in one chat was still in the field, caret and
    // all, once another conversation had loaded around it.
    const { rerender } = render(<Stage sessionId="a" arrival={1} seed={{ b: "the other chat's line" }} />);
    fireEvent.change(field(), { target: { value: "half a question" } });
    rerender(<Stage sessionId="b" arrival={2} seed={{ b: "the other chat's line" }} />);
    expect(field().value).toBe("the other chat's line");
    // A chat nobody has typed into arrives on an empty field rather than on another chat's text.
    rerender(<Stage sessionId="c" arrival={3} seed={{ b: "the other chat's line" }} />);
    expect(field().value).toBe("");
    // Back on the first chat, its own sentence is still in the field.
    rerender(<Stage sessionId="a" arrival={4} seed={{ b: "the other chat's line" }} />);
    expect(field().value).toBe("half a question");
  });

  it("offers a restored draft at its end, which is where the next character goes", () => {
    // The caret lands after the last word rather than at the offset the writer left it at, which is
    // where the next character goes when someone returns to a half-typed sentence. It is what a
    // textarea does when its value is assigned, and a swap makes that assignment because the text
    // differs. A keystroke's text does not differ, so the caret stays where it is mid-sentence; that
    // half was measured in Chromium, since `fireEvent.change` moves the caret itself and jsdom
    // cannot reproduce it.
    const seed = { a: "half a question", b: "a much longer sentence in the other chat" };
    const { rerender } = render(<Stage sessionId="a" arrival={1} seed={seed} />);
    rerender(<Stage sessionId="b" arrival={2} seed={seed} />);
    expect([field().value, field().selectionStart]).toEqual([seed.b, seed.b.length]);
    rerender(<Stage sessionId="a" arrival={3} seed={seed} />);
    expect([field().value, field().selectionStart]).toEqual([seed.a, seed.a.length]);
  });

  it("never empties its own field: a send the state refuses leaves the words standing", () => {
    // The field is emptied by the state that holds it, which spends a draft only when a turn
    // actually starts. Pressing Enter into a busy panel used to blank the field regardless.
    const onSubmit = vi.fn();
    render(<Stage busy={true} onSubmit={onSubmit} seed={{ a: "half a question" }} />);
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
    expect(field().value).toBe("half a question");
  });

  it("hands a blank field's whitespace to the state rather than swallowing it", () => {
    const onSubmit = vi.fn();
    render(<Stage onSubmit={onSubmit} seed={{ a: "   " }} />);
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledWith("   ");
    expect(field().value).toBe("   ");
  });

  it("sends on the send button and lights it only with text", () => {
    const onSubmit = vi.fn();
    render(<Stage onSubmit={onSubmit} />);
    expect(screen.getByLabelText("Send").className).not.toContain("live");
    fireEvent.change(field(), { target: { value: "hi" } });
    expect(screen.getByLabelText("Send").className).toContain("live");
    fireEvent.click(screen.getByLabelText("Send"));
    expect(onSubmit).toHaveBeenCalledWith("hi");
  });

  it("becomes a stop button while busy: it cancels the turn and never submits", () => {
    const onSubmit = vi.fn();
    const onStop = vi.fn();
    render(<Stage busy={true} onSubmit={onSubmit} onStop={onStop} />);
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
    const { rerender } = render(<Stage />);
    expect(document.activeElement).not.toBe(field());
    rerender(<Stage arrival={0} />);
    expect(document.activeElement).toBe(field());
    // The panel clips its overflow, which makes it a scroll box the user cannot scroll and the
    // engine can, and bringing a newly focused element into view is when it does. Coming back from
    // the console this field is below the panel's clipped edge for the length of the ease, so the
    // panel was scrolled to reach it and every row in the window lurched up: `panel.scrollTop` went
    // 0 to 139 in the frame focus landed, traced at 640x720 with the session list open.
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    focus.mockRestore();
  });

  it("takes focus again when another conversation arrives, but not on any other render", () => {
    const composer = (arrival: number | null) => <Stage arrival={arrival} />;
    const { rerender } = render(composer(3));
    expect(document.activeElement).toBe(field());
    // A reader who has moved elsewhere in the panel keeps their place: a stream re-rendering the
    // chat around an unchanged draft must not take the caret back.
    (document.activeElement as HTMLElement).blur();
    rerender(composer(3));
    expect(document.activeElement).not.toBe(field());
    // A chat arriving is the case that moves the caret. The gestures that cause one are pressed
    // inside sections the swap removes (a switcher row, a reminder's open control, a delete
    // confirm), so without this the control pressed stops existing and focus falls to `<body>`.
    rerender(composer(4));
    expect(document.activeElement).toBe(field());
    // A chat arriving while the console is over the chat, or while the panel is shut, moves no
    // caret, because this field is not on screen to receive one.
    (document.activeElement as HTMLElement).blur();
    rerender(composer(null));
    rerender(composer(null));
    expect(document.activeElement).not.toBe(field());
  });

  it("auto-grows with its content up to the cap, then holds and scrolls", () => {
    render(<Stage arrival={0} />);
    fakeMetrics(34, () => 64);
    fireEvent.change(field(), { target: { value: "two\nlines" } });
    expect(field().style.height).toBe("64px");
    fakeMetrics(34, () => 400);
    fireEvent.change(field(), { target: { value: "far\ntoo\nmany\nlines\nnow\nreally" } });
    expect(field().style.height).toBe("120px");
  });

  it("keeps the button beside the field on one line and drops it below once it wraps", () => {
    render(<Stage arrival={0} />);
    fakeMetrics(34, () => 34);
    fireEvent.change(field(), { target: { value: "one line" } });
    expect(pill().className).toBe("composer");
    fakeMetrics(34, () => 50);
    fireEvent.change(field(), { target: { value: "one line\nand a second" } });
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("50px");
  });

  it("decides the layout at the inline width, so a draft in the band cannot flip-flop", () => {
    render(<Stage arrival={0} />);
    // This draft is inside the band: it needs two lines while the button holds its column beside
    // the field, and one once the button drops below and gives that width back. Measured at the
    // width in use, the two layouts would keep switching between each other.
    fakeMetrics(34, (stacked) => (stacked ? 34 : 50));
    fireEvent.change(field(), { target: { value: "a draft that only just wraps" } });
    expect(pill().className).toBe("composer stacked");
    // Sized for the layout it chose (one line at the full width) rather than for the inline layout
    // it measured at.
    expect(field().style.height).toBe("34px");
    // Still stacked a keystroke later, because the layout follows the text and not the layout on
    // screen.
    fireEvent.change(field(), { target: { value: "a draft that only just wraps!" } });
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("34px");
  });

  it("pins the pill's floor for the measurement and hands it back afterwards", () => {
    render(<Stage arrival={0} />);
    fakeMetrics(34, () => 34);
    fireEvent.change(field(), { target: { value: "one line" } });
    // The measurement collapses the field and removes the layout class, and at the panel's ceiling
    // that lets the pill shrink to its smaller automatic minimum while the log above grows into the
    // gap, which loses the log's scroll position permanently. jsdom has no layout to reproduce that
    // in, so this test asserts the condition the browser enforces with pixels: at the instant the
    // field is measured, the pill still stands at the height it had on entry.
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
    // The floor lasts only for the measurement: the pill sizes itself again on the way out.
    expect(pill().style.minHeight).toBe("");
  });

  it("tells the container when the pill resizes, and stays quiet when it only retypes", () => {
    const onResize = vi.fn();
    render(<Stage arrival={0} onResize={onResize} />);
    // A draft inside one line leaves the pill the size it was, so nothing is reported. This is the
    // case that must stay quiet, since every keystroke of a short message passes through here.
    fakeMetrics(34, () => 34);
    fireEvent.change(field(), { target: { value: "one line" } });
    onResize.mockClear();
    fireEvent.change(field(), { target: { value: "one line still" } });
    expect(onResize).not.toHaveBeenCalled();
    // Restacking is a resize, because the button takes a row of its own, and so is a further line
    // after it. The log above uses the report to hold its tail, which the taller pill now covers
    // more of.
    fakeMetrics(34, () => 50);
    fireEvent.change(field(), { target: { value: "one line\nand a second" } });
    expect(onResize).toHaveBeenCalledOnce();
    fakeMetrics(34, () => 66);
    fireEvent.change(field(), { target: { value: "one line\nand a second\nand a third" } });
    expect(onResize).toHaveBeenCalledTimes(2);
  });

  it("re-measures when the viewport resizes, since the answer belongs to a width", () => {
    const onResize = vi.fn();
    render(<Stage arrival={0} onResize={onResize} />);
    // A draft that fits one line at the width it was typed at.
    let narrow = false;
    fakeMetrics(34, () => (narrow ? 50 : 34));
    fireEvent.change(field(), { target: { value: "a draft that fits one line at the wide panel" } });
    expect(pill().className).toBe("composer");
    expect(field().style.height).toBe("34px");
    onResize.mockClear();
    // The panel narrows under an unchanged draft: the same text now wraps, and nothing was typed.
    // While a keystroke was the only trigger, this left the field scrolled inside a box sized for a
    // line that no longer fits, with the button still holding its column beside it.
    narrow = true;
    fireEvent(window, new Event("resize"));
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("50px");
    // The pill did change size, so the log above is told about it as it is for a keystroke that
    // grows the pill.
    expect(onResize).toHaveBeenCalledOnce();
  });

  it("stops listening for resizes once it is gone", () => {
    const { unmount } = render(<Stage arrival={0} />);
    // The measurement reads and writes the two nodes this component owns, and React nulls those
    // refs on unmount, so a listener left behind does more than waste a frame: the first resize
    // after the panel is gone throws on a null field. Without the cleanup this test catches that
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
    render(<Stage arrival={0} />);
    fakeMetrics(34, (stacked) => (field().value === "" ? 34 : stacked ? 50 : 66));
    fireEvent.change(field(), { target: { value: "a draft\nover two lines" } });
    expect(pill().className).toBe("composer stacked");
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(pill().className).toBe("composer");
    expect(field().style.height).toBe("34px");
  });
});
