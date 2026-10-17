import { describe, expect, it } from "vitest";

import type { TurnEvent } from "../bridge/types";
import type { Action } from "./overlayState";
import { initialState, reduce } from "./overlayState";

const run = (actions: Action[]) => actions.reduce(reduce, initialState);
const assistant = (s: ReturnType<typeof run>) => s.messages.find((m) => m.role === "assistant");
const event = (e: TurnEvent): Action => ({ kind: "event", event: e });
const beat = (wait: string, detail: string): Action => event({ kind: "heartbeat", wait, detail });
const submit: Action = { kind: "submit", text: "q" };

describe("a heartbeat's wait", () => {
  it("sets the chip to the brain's sentence and key", () => {
    const s = run([submit, beat("queued", "2 subtasks waiting for room to run")]);
    expect(assistant(s)).toMatchObject({
      status: "2 subtasks waiting for room to run",
      statusState: "queued",
    });
  });

  it("replaces a chip a dropped status left behind", () => {
    const s = run([
      submit,
      event({ kind: "status", state: "calling", detail: "waiting for a tool to finish" }),
      beat("delegating", "1 subtask running"),
    ]);
    expect(assistant(s)).toMatchObject({ status: "1 subtask running", statusState: "delegating" });
  });

  it("never adds its thinking sentence to the thoughts", () => {
    const s = run([submit, beat("thinking", "working out the reply")]);
    expect(assistant(s)).toMatchObject({ status: "working out the reply", statusState: "thinking" });
    expect(assistant(s)?.thoughts).toBe("");
  });

  it("keeps the latest reasoning on a chip that already shows thinking", () => {
    const s = run([
      submit,
      event({ kind: "status", state: "thinking", detail: "the user wants" }),
      beat("thinking", "working out the reply"),
    ]);
    expect(assistant(s)).toMatchObject({ status: "the user wants", statusState: "thinking" });
    expect(assistant(s)?.thoughts).toBe("the user wants");
  });

  it("clears a chip other than thinking when the turn waits on nothing", () => {
    const s = run([
      submit,
      event({ kind: "status", state: "swapping", detail: "loading" }),
      beat("", ""),
    ]);
    expect(assistant(s)).toMatchObject({ status: null, statusState: null, streaming: true });
  });

  it("keeps the latest reasoning when the turn waits on nothing", () => {
    const s = run([
      submit,
      event({ kind: "status", state: "thinking", detail: "the user wants" }),
      beat("", ""),
    ]);
    expect(assistant(s)).toMatchObject({ status: "the user wants", statusState: "thinking" });
  });
});

describe("an empty status", () => {
  const queued = event({
    kind: "status",
    state: "queued",
    detail: "waiting for this chat's previous message to finish",
  });
  const cleared = event({ kind: "status", state: "", detail: "" });

  it("clears the chip the wait before it left", () => {
    const s = run([submit, queued, cleared]);
    expect(assistant(s)).toMatchObject({ status: null, statusState: null, streaming: true });
  });

  it("clears a reasoning chip and keeps its thoughts", () => {
    const reasoned = event({ kind: "status", state: "thinking", detail: "rivers" });
    const s = run([submit, reasoned, cleared]);
    expect(assistant(s)).toMatchObject({ status: null, statusState: null, thoughts: "rivers" });
  });

  it("leaves the reply's text, its tool chip and an approval card in place", () => {
    const s = run([
      submit,
      event({ kind: "delta", text: "The Rhine" }),
      event({ kind: "toolActivity", toolName: "send_email", summary: "to a friend" }),
      event({
        kind: "confirmRequest",
        confirmId: "c-1",
        toolName: "send_email",
        argumentsJson: "{}",
        reason: "it sends mail",
      }),
      queued,
      cleared,
    ]);
    expect(assistant(s)).toMatchObject({ content: "The Rhine", tool: "send_email: to a friend" });
    expect(s.pendingConfirm?.confirmId).toBe("c-1");
  });
});
