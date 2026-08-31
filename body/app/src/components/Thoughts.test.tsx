import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Thoughts } from "./Thoughts";

describe("Thoughts", () => {
  it("starts shut, with a real button that says so", () => {
    const { container } = render(<Thoughts trace="step one" />);
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
    expect(container.querySelector(".thoughts-body")).toBeNull();
  });

  it("rolls the body rather than swapping it in, so the panel can follow the same motion", () => {
    const { container } = render(<Thoughts trace="step one" />);
    fireEvent.click(screen.getByRole("button", { name: "Thoughts" }));
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
