import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "./Composer";

const field = () => screen.getByLabelText("Message") as HTMLTextAreaElement;

describe("Composer", () => {
  it("sends on Enter and clears, but Shift+Enter and other keys do not", () => {
    const onSubmit = vi.fn();
    render(<Composer busy={false} active={false} onSubmit={onSubmit} onStop={vi.fn()} />);
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
    render(<Composer busy={false} active={false} onSubmit={onSubmit} onStop={vi.fn()} />);
    expect(screen.getByLabelText("Send").className).not.toContain("live");
    fireEvent.change(field(), { target: { value: "hi" } });
    expect(screen.getByLabelText("Send").className).toContain("live");
    fireEvent.click(screen.getByLabelText("Send"));
    expect(onSubmit).toHaveBeenCalledWith("hi");
  });

  it("becomes a stop button while busy: it cancels the turn and never submits", () => {
    const onSubmit = vi.fn();
    const onStop = vi.fn();
    render(<Composer busy={true} active={false} onSubmit={onSubmit} onStop={onStop} />);
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

  it("takes focus when the panel opens (focus-on-summon)", () => {
    const { rerender } = render(
      <Composer busy={false} active={false} onSubmit={vi.fn()} onStop={vi.fn()} />,
    );
    expect(document.activeElement).not.toBe(field());
    rerender(<Composer busy={false} active={true} onSubmit={vi.fn()} onStop={vi.fn()} />);
    expect(document.activeElement).toBe(field());
  });

  it("auto-grows with its content up to the cap, then holds and scrolls", () => {
    render(<Composer busy={false} active={true} onSubmit={vi.fn()} onStop={vi.fn()} />);
    Object.defineProperty(field(), "scrollHeight", { configurable: true, value: 64 });
    fireEvent.change(field(), { target: { value: "two\nlines" } });
    expect(field().style.height).toBe("64px");
    Object.defineProperty(field(), "scrollHeight", { configurable: true, value: 400 });
    fireEvent.change(field(), { target: { value: "far\ntoo\nmany\nlines\nnow\nreally" } });
    expect(field().style.height).toBe("120px");
  });
});
