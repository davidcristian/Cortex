import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Message as MessageModel } from "../overlay/overlayState";
import { Message } from "./Message";

const grow = (): void => undefined;

/** Renders under test with the tail pin every real caller supplies. */
function Show({ message }: { readonly message: MessageModel }) {
  return <Message message={message} onGrow={grow} />;
}

const msg = (over: Partial<MessageModel>): MessageModel => ({
  id: "m",
  role: "assistant",
  content: "",
  streaming: false,
  tool: null,
  status: null,
  statusState: null,
  thoughts: "",
  error: null,
  ...over,
});

// A streaming message mounts the whisper's clock; its frames are swallowed here (the clock has
// its own tests) so these stay about what the message renders.
beforeEach(() => {
  vi.spyOn(window, "requestAnimationFrame").mockReturnValue(1);
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Message", () => {
  it("renders a user bubble as plain text", () => {
    const { container } = render(<Show message={msg({ role: "user", content: "hey there" })} />);
    const bubble = container.querySelector(".bubble");
    expect(bubble?.className).toContain("b-user");
    expect(bubble?.textContent).toBe("hey there");
    expect(container.querySelector(".ch")).toBeNull();
  });

  it("whispers a streaming reply: the mist rides the bubble and no caret exists", () => {
    const { container } = render(
      <Show message={msg({ content: "typing now", streaming: true })} />,
    );
    expect(container.querySelector(".bubble")?.className).toContain("whisper");
    expect(container.querySelector(".mist")).not.toBeNull();
    expect(container.querySelector(".caret")).toBeNull();
  });

  it("renders a finished assistant bubble plain, with nothing still working", () => {
    const { container } = render(<Show message={msg({ content: "all done" })} />);
    expect(container.querySelector(".mist")).toBeNull();
    expect(container.querySelector(".bubble")?.textContent).toBe("all done");
  });

  it("renders an error as an alert", () => {
    render(<Show message={msg({ error: "cannot reach the brain" })} />);
    expect(screen.getByRole("alert").textContent).toBe("cannot reach the brain");
  });

  it("holds the breath mist in the bubble until the first token arrives", () => {
    const { container } = render(<Show message={msg({ streaming: true })} />);
    expect(container.querySelector(".bubble")?.className).toContain("w-breath");
    expect(container.querySelector(".mist i")).not.toBeNull();
    expect(container.querySelector(".sr-copy")?.textContent).toBe("Thinking");
  });

  it("renders live tool and status activity as chips above the streaming bubble", () => {
    const { container } = render(
      <Show
        message={msg({
          content: "working",
          streaming: true,
          tool: "read_email: reading inbox",
          status: "thinking it over",
        })}
      />,
    );
    const chips = [...container.querySelectorAll(".chip")];
    expect(chips.map((chip) => chip.textContent)).toEqual([
      "read_email: reading inbox",
      "thinking it over",
    ]);
  });

  it("marks a thinking status chip distinctly from a generic status chip", () => {
    const { container } = render(
      <Show
        message={msg({ content: "x", streaming: true, status: "reasoning", statusState: "thinking" })}
      />,
    );
    const chip = container.querySelector(".chip");
    expect(chip?.className).toContain("chip-think");
    expect(chip?.getAttribute("aria-label")).toBe("Thinking");
  });

  it("leaves a non-thinking status chip plain", () => {
    const { container } = render(
      <Show
        message={msg({ content: "x", streaming: true, status: "swapping", statusState: "load" })}
      />,
    );
    const chip = container.querySelector(".chip");
    expect(chip?.className).not.toContain("chip-think");
    expect(chip?.getAttribute("aria-label")).toBeNull();
  });

  it("drops the chips once the turn settles", () => {
    const { container } = render(
      <Show
        message={msg({ content: "done", streaming: false, tool: "read_email: read", status: "s" })}
      />,
    );
    expect(container.querySelector(".chip")).toBeNull();
  });

  it("offers a collapsed thoughts disclosure on a settled reply that reasoned", () => {
    const { container } = render(
      <Show message={msg({ content: "done", streaming: false, thoughts: "step one\nstep two" })} />,
    );
    expect(container.querySelector(".thoughts")).not.toBeNull();
    const control = screen.getByRole("button", { name: "Thoughts" });
    expect(control).toHaveAttribute("aria-expanded", "false"); // collapsed by default
    // The trace itself is the message's own, so opening it is what proves it was handed down whole:
    // the body is not in the DOM at all while the disclosure is shut.
    expect(container.querySelector(".thoughts-body")).toBeNull();
    fireEvent.click(control);
    expect(container.querySelector(".thoughts-body")?.textContent).toBe("step one\nstep two");
  });

  it("hides the thoughts disclosure while streaming (the live chip owns deliberation then)", () => {
    const { container } = render(
      <Show message={msg({ content: "x", streaming: true, thoughts: "partial reasoning" })} />,
    );
    expect(container.querySelector(".thoughts")).toBeNull();
  });

  it("shows no thoughts disclosure on a settled reply that never reasoned", () => {
    const { container } = render(
      <Show message={msg({ content: "done", streaming: false, thoughts: "" })} />,
    );
    expect(container.querySelector(".thoughts")).toBeNull();
  });

  it("settles the live thinking chip into the disclosure in place, one row for one row", () => {
    // The stylesheet gives both of these the same height (`--trace-row`) so that a turn completing
    // swaps them without resizing the log under them: traced at 60Hz, unequal boxes eased the whole
    // panel down 4px at the moment the answer landed. That only holds while the two really are one
    // row in two states, which is a structural contract no stylesheet can defend. Adding a second
    // settled row, or leaving the chip's slot empty, puts the shrink back.
    const reasoning = { streaming: true, status: "reasoning", statusState: "thinking" } as const;
    const live = render(<Show message={msg({ ...reasoning, thoughts: "step one" })} />).container;
    expect(live.querySelectorAll(".chip")).toHaveLength(1);
    expect(live.querySelector(".chip")?.nextElementSibling?.className).toContain("bubble");
    cleanup();
    const settled = render(
      <Show message={msg({ ...reasoning, streaming: false, thoughts: "step one" })} />,
    ).container;
    expect(settled.querySelectorAll(".thoughts")).toHaveLength(1);
    expect(settled.querySelector(".thoughts")?.nextElementSibling?.className).toContain("bubble");
  });

  it("publishes the row height off whichever chip the turn shows", () => {
    // The other half of the contract above. The disclosure matches the chip because the chip says
    // how tall it is (`--trace-row`, overlay/measured.ts), so the pairing survives a change to the
    // chip's padding or font that nobody thinks to re-derive a constant for. Both chips are the
    // same box and either may be the only one a turn shows, so both have to say so.
    const laid = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetHeight");
    Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
      configurable: true,
      get: () => 28,
    });
    try {
      render(<Show message={msg({ streaming: true, status: "reasoning" })} />);
      expect(document.documentElement.style.getPropertyValue("--trace-row")).toBe("28px");
      document.documentElement.style.removeProperty("--trace-row");
      cleanup();
      render(<Show message={msg({ streaming: true, tool: "read_email" })} />);
      expect(document.documentElement.style.getPropertyValue("--trace-row")).toBe("28px");
    } finally {
      document.documentElement.style.removeProperty("--trace-row");
      if (laid !== undefined) {
        Object.defineProperty(HTMLElement.prototype, "offsetHeight", laid);
      }
    }
  });
});
