import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PendingConfirm } from "../overlay/overlayState";
import { ConfirmCard } from "./ConfirmCard";

const confirm = (over: Partial<PendingConfirm> = {}): PendingConfirm => ({
  confirmId: "c-1",
  toolName: "send_email",
  argumentsJson: '{"to":"ada@example.com","subject":"Hi","body":"Hello Ada"}',
  reason: "this action is outbound or irreversible and runs only with your approval",
  ...over,
});

describe("ConfirmCard", () => {
  it("shows the tool, the draft as key→value lines, and the reason verbatim", () => {
    render(<ConfirmCard confirm={confirm()} onRespond={vi.fn()} />);
    expect(screen.getByRole("group", { name: "Approval required" })).toBeInTheDocument();
    expect(screen.getByText("send_email")).toBeInTheDocument();
    expect(screen.getByText("to")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("subject")).toBeInTheDocument();
    expect(screen.getByText("Hi")).toBeInTheDocument();
    expect(
      screen.getByText("this action is outbound or irreversible and runs only with your approval"),
    ).toBeInTheDocument();
  });

  it("renders non-string values as their JSON. The draft shown is the draft that runs", () => {
    render(
      <ConfirmCard
        confirm={confirm({ argumentsJson: '{"count":3,"tags":["a","b"]}' })}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText('["a","b"]')).toBeInTheDocument();
  });

  it("falls back to the raw string when the arguments are not valid JSON", () => {
    render(<ConfirmCard confirm={confirm({ argumentsJson: "{oops" })} onRespond={vi.fn()} />);
    expect(screen.getByText("{oops")).toBeInTheDocument();
  });

  it("falls back to the raw string when the JSON is not one object (array, scalar, null)", () => {
    for (const raw of ['["a"]', '"text"', "null"]) {
      const { unmount } = render(
        <ConfirmCard confirm={confirm({ argumentsJson: raw })} onRespond={vi.fn()} />,
      );
      expect(screen.getByText(raw)).toBeInTheDocument();
      unmount();
    }
  });

  it("Approve answers true and Deny answers false, each with the confirm id", () => {
    const onRespond = vi.fn();
    render(<ConfirmCard confirm={confirm()} onRespond={onRespond} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(onRespond).toHaveBeenCalledWith("c-1", true);
    fireEvent.click(screen.getByText("Deny"));
    expect(onRespond).toHaveBeenCalledWith("c-1", false);
    expect(onRespond).toHaveBeenCalledTimes(2);
  });
});
