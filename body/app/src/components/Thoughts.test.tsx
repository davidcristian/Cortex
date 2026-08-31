import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Thoughts } from "./Thoughts";

describe("Thoughts", () => {
  it("starts shut, with a real button that says so", () => {
    const { container } = render(<Thoughts trace="step one" />);
    // No longer a `<summary>` in a `<details>`, because the roll needs an element whose height
    // something else can animate, and the semantics have to survive that change.
    expect(screen.getByRole("button", { name: "Thoughts" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(container.querySelector(".thoughts-body")).toBeNull();
  });

  it("reveals the trace on the button, and hides it again", () => {
    const { container } = render(<Thoughts trace={"step one\nstep two"} />);
    const control = screen.getByRole("button", { name: "Thoughts" });
    fireEvent.click(control);
    expect(control).toHaveAttribute("aria-expanded", "true");
    expect(container.querySelector(".thoughts-body")?.textContent).toBe("step one\nstep two");
    fireEvent.click(control);
    expect(control).toHaveAttribute("aria-expanded", "false");
    // The body is gone rather than merely hidden. `Collapse` holds it only long enough to roll it
    // shut, which in a DOM with no layout is no time at all.
    expect(container.querySelector(".thoughts-body")).toBeNull();
  });

  it("rolls the body rather than swapping it in, so the panel can follow the same motion", () => {
    const { container } = render(<Thoughts trace="step one" />);
    fireEvent.click(screen.getByRole("button", { name: "Thoughts" }));
    // The wrapper carries the height animation and the `data-morphing` contract with it. A body
    // rendered as a bare sibling of the button would open in one frame, which is the defect this
    // component was rebuilt to fix.
    expect(container.querySelector(".collapse > .thoughts-body")).not.toBeNull();
  });

  it("names the body it controls, so the button and the trace are one thing", () => {
    const { container } = render(<Thoughts trace="step one" />);
    const control = screen.getByRole("button", { name: "Thoughts" });
    fireEvent.click(control);
    const body = container.querySelector(".thoughts-body");
    expect(control.getAttribute("aria-controls")).toBe(body?.id);
    expect(body?.id).not.toBe("");
  });

  it("points at nothing while shut, the body it would name not being in the document", () => {
    // `Collapse` removes the body once it has rolled shut, so an `aria-controls` left set would
    // name an id no element has. `aria-expanded` is what carries the state either way.
    const { container } = render(<Thoughts trace="step one" />);
    const control = screen.getByRole("button", { name: "Thoughts" });
    expect(control).not.toHaveAttribute("aria-controls");
    fireEvent.click(control);
    fireEvent.click(control);
    expect(container.querySelector(".thoughts-body")).toBeNull();
    expect(control).not.toHaveAttribute("aria-controls");
  });

  it("gives each reply's trace its own id, since a chat shows many at once", () => {
    render(
      <>
        <Thoughts trace="first" />
        <Thoughts trace="second" />
      </>,
    );
    const [one, two] = screen.getAllByRole("button", { name: "Thoughts" });
    fireEvent.click(one!);
    fireEvent.click(two!);
    expect(one?.getAttribute("aria-controls")).not.toBe(two?.getAttribute("aria-controls"));
    expect(one?.getAttribute("aria-controls")).not.toBeNull();
  });

  it("renders the trace as plain text and linkifies nothing in it", () => {
    // The trace is model output, and the overlay never parses markup or turns a URL into a link
    // anywhere it renders text (ADR-0020). Moving the trace out of `<details>` must not have given
    // it a renderer.
    const trace = "visited https://example.com/x and <b>weighed</b> it";
    const { container } = render(<Thoughts trace={trace} />);
    fireEvent.click(screen.getByRole("button", { name: "Thoughts" }));
    const body = container.querySelector(".thoughts-body");
    expect(body?.textContent).toBe(trace);
    expect(body?.querySelector("a")).toBeNull();
    expect(body?.querySelector("b")).toBeNull();
  });

  it("keeps one trace's state to itself when a sibling is opened", () => {
    render(
      <>
        <Thoughts trace="first" />
        <Thoughts trace="second" />
      </>,
    );
    const [one, two] = screen.getAllByRole("button", { name: "Thoughts" });
    fireEvent.click(one!);
    expect(one).toHaveAttribute("aria-expanded", "true");
    expect(two).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("second")).toBeNull();
  });
});
