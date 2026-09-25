import { fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { draftOf, dropDraft, parkDraft } from "../overlay/drafts";
import type { Picture } from "../overlay/pictures";
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
  readonly pictures?: readonly Picture[];
  readonly pictureNote?: string | null;
  readonly onAttach?: (files: readonly Blob[]) => void;
  readonly onDetach?: (id: string) => void;
}

/** The composer holds no text of its own, so a test that types needs the state that does. */
function Stage({
  sessionId = "a",
  busy = false,
  arrival = null,
  seed = {},
  onSubmit = () => undefined,
  onStop = () => undefined,
  onResize = () => undefined,
  pictures = [],
  pictureNote = null,
  onAttach = () => undefined,
  onDetach = () => undefined,
}: StageProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>(seed);
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
      pictures={pictures}
      pictureNote={pictureNote}
      onAttach={onAttach}
      onDetach={onDetach}
    />
  );
}

/** jsdom has no layout, so the field is given the two numbers the effect reads. */
function fakeMetrics(oneLine: number, needs: (stacked: boolean) => number) {
  Object.defineProperty(field(), "clientHeight", { configurable: true, value: oneLine });
  Object.defineProperty(field(), "scrollHeight", {
    configurable: true,
    get(this: HTMLTextAreaElement) {
      return needs((this.parentElement as HTMLElement).classList.contains("stacked"));
    },
  });
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
    const { rerender } = render(<Stage sessionId="a" arrival={1} seed={{ b: "the other chat's line" }} />);
    fireEvent.change(field(), { target: { value: "half a question" } });
    rerender(<Stage sessionId="b" arrival={2} seed={{ b: "the other chat's line" }} />);
    expect(field().value).toBe("the other chat's line");
    rerender(<Stage sessionId="c" arrival={3} seed={{ b: "the other chat's line" }} />);
    expect(field().value).toBe("");
    rerender(<Stage sessionId="a" arrival={4} seed={{ b: "the other chat's line" }} />);
    expect(field().value).toBe("half a question");
  });

  it("offers a restored draft at its end, which is where the next character goes", () => {
    const seed = { a: "half a question", b: "a much longer sentence in the other chat" };
    const { rerender } = render(<Stage sessionId="a" arrival={1} seed={seed} />);
    rerender(<Stage sessionId="b" arrival={2} seed={seed} />);
    expect([field().value, field().selectionStart]).toEqual([seed.b, seed.b.length]);
    rerender(<Stage sessionId="a" arrival={3} seed={seed} />);
    expect([field().value, field().selectionStart]).toEqual([seed.a, seed.a.length]);
  });

  it("never empties its own field: a send the state refuses leaves the words in place", () => {
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
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("takes focus when the panel opens (focus-on-summon), and scrolls nothing to do it", () => {
    const focus = vi.spyOn(HTMLTextAreaElement.prototype, "focus");
    const { rerender } = render(<Stage />);
    expect(document.activeElement).not.toBe(field());
    rerender(<Stage arrival={0} />);
    expect(document.activeElement).toBe(field());
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    focus.mockRestore();
  });

  it("takes focus again when another conversation arrives, but not on any other render", () => {
    const composer = (arrival: number | null) => <Stage arrival={arrival} />;
    const { rerender } = render(composer(3));
    expect(document.activeElement).toBe(field());
    (document.activeElement as HTMLElement).blur();
    rerender(composer(3));
    expect(document.activeElement).not.toBe(field());
    rerender(composer(4));
    expect(document.activeElement).toBe(field());
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
    fakeMetrics(34, (stacked) => (stacked ? 34 : 50));
    fireEvent.change(field(), { target: { value: "a draft that only just wraps" } });
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("34px");
    fireEvent.change(field(), { target: { value: "a draft that only just wraps!" } });
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("34px");
  });

  it("fixes the pill's floor for the measurement and hands it back afterwards", () => {
    render(<Stage arrival={0} />);
    fakeMetrics(34, () => 34);
    fireEvent.change(field(), { target: { value: "one line" } });
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
    expect(pill().style.minHeight).toBe("");
  });

  it("tells the container when the pill resizes, and stays quiet when it only retypes", () => {
    const onResize = vi.fn();
    render(<Stage arrival={0} onResize={onResize} />);
    fakeMetrics(34, () => 34);
    fireEvent.change(field(), { target: { value: "one line" } });
    onResize.mockClear();
    fireEvent.change(field(), { target: { value: "one line still" } });
    expect(onResize).not.toHaveBeenCalled();
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
    let narrow = false;
    fakeMetrics(34, () => (narrow ? 50 : 34));
    fireEvent.change(field(), { target: { value: "a draft that fits one line at the wide panel" } });
    expect(pill().className).toBe("composer");
    expect(field().style.height).toBe("34px");
    onResize.mockClear();
    narrow = true;
    fireEvent(window, new Event("resize"));
    expect(pill().className).toBe("composer stacked");
    expect(field().style.height).toBe("50px");
    expect(onResize).toHaveBeenCalledOnce();
  });

  it("stops listening for resizes once it is gone", () => {
    const { unmount } = render(<Stage arrival={0} />);
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
