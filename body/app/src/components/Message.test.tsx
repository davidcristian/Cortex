import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Message as MessageModel } from "../overlay/overlayState";
import { Message } from "./Message";

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

describe("Message", () => {
  it("renders a user bubble", () => {
    const { container } = render(<Message message={msg({ role: "user", content: "hey there" })} />);
    expect(container.querySelector(".bubble")?.className).toContain("b-user");
  });

  it("renders a streaming assistant bubble with a caret", () => {
    const { container } = render(<Message message={msg({ content: "typing now", streaming: true })} />);
    expect(container.querySelector(".bubble")?.className).toContain("streaming");
    expect(container.querySelector(".caret")).not.toBeNull();
  });

  it("renders a finished assistant bubble without a caret", () => {
    const { container } = render(<Message message={msg({ content: "all done", streaming: false })} />);
    expect(container.querySelector(".caret")).toBeNull();
    expect(container.querySelector(".bubble")?.className).not.toContain("streaming");
  });

  it("renders an error as an alert", () => {
    render(<Message message={msg({ error: "cannot reach the brain" })} />);
    expect(screen.getByRole("alert").textContent).toBe("cannot reach the brain");
  });

  it("holds a thinking shimmer in the bubble until the first token arrives", () => {
    const { container } = render(<Message message={msg({ streaming: true })} />);
    expect(container.querySelector(".thinking")).not.toBeNull();
    expect(container.querySelector(".caret")).toBeNull();
  });

  it("renders live tool and status activity as chips above the streaming bubble", () => {
    const { container } = render(
      <Message
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
      <Message
        message={msg({ content: "x", streaming: true, status: "reasoning", statusState: "thinking" })}
      />,
    );
    const chip = container.querySelector(".chip");
    expect(chip?.className).toContain("chip-think");
    expect(chip?.getAttribute("aria-label")).toBe("Thinking");
  });

  it("leaves a non-thinking status chip plain", () => {
    const { container } = render(
      <Message
        message={msg({ content: "x", streaming: true, status: "swapping", statusState: "load" })}
      />,
    );
    const chip = container.querySelector(".chip");
    expect(chip?.className).not.toContain("chip-think");
    expect(chip?.getAttribute("aria-label")).toBeNull();
  });

  it("drops the chips once the turn settles", () => {
    const { container } = render(
      <Message
        message={msg({ content: "done", streaming: false, tool: "read_email: read", status: "s" })}
      />,
    );
    expect(container.querySelector(".chip")).toBeNull();
  });

  it("offers a collapsed thoughts disclosure on a settled reply that reasoned", () => {
    const { container } = render(
      <Message message={msg({ content: "done", streaming: false, thoughts: "step one\nstep two" })} />,
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
      <Message message={msg({ content: "x", streaming: true, thoughts: "partial reasoning" })} />,
    );
    expect(container.querySelector(".thoughts")).toBeNull();
  });

  it("shows no thoughts disclosure on a settled reply that never reasoned", () => {
    const { container } = render(
      <Message message={msg({ content: "done", streaming: false, thoughts: "" })} />,
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
    const live = render(<Message message={msg({ ...reasoning, thoughts: "step one" })} />).container;
    expect(live.querySelectorAll(".chip")).toHaveLength(1);
    expect(live.querySelector(".chip")?.nextElementSibling?.className).toContain("bubble");
    cleanup();
    const settled = render(
      <Message message={msg({ ...reasoning, streaming: false, thoughts: "step one" })} />,
    ).container;
    expect(settled.querySelectorAll(".thoughts")).toHaveLength(1);
    expect(settled.querySelector(".thoughts")?.nextElementSibling?.className).toContain("bubble");
  });
});
