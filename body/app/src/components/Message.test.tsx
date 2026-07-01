import { render, screen } from "@testing-library/react";
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
});
