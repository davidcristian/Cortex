import { describe, expect, it } from "vitest";

import type { TransportError } from "../bridge/types";
import {
  INITIAL_LINK,
  type LinkView,
  describeLink,
  linkFailed,
  linkObserved,
  linkProbeEnded,
  linkProbing,
  linkServing,
} from "./linkState";

const view = (over: Partial<LinkView> = {}): LinkView => ({ ...INITIAL_LINK, ...over });
const ready = view({ state: "ready", detail: "cortex-orchestrator 0.1.0" });
const down = view({ state: "down", detail: "connection refused" });

describe("link state", () => {
  it("starts claiming nothing at all", () => {
    // The honest opening position: an indicator that says "ready" before it has asked is the
    // decoration the v1 dot was.
    expect(INITIAL_LINK).toEqual({ state: "unknown", detail: "", probing: false });
  });

  it("a probe in flight keeps the last known state and marks the wait", () => {
    expect(linkProbing(down)).toEqual({ ...down, probing: true });
    expect(linkProbing(INITIAL_LINK)).toEqual({ ...INITIAL_LINK, probing: true });
  });

  it("an answered probe replaces both facts", () => {
    expect(linkObserved({ state: "degraded", detail: "loading" })).toEqual({
      state: "degraded",
      detail: "loading",
      probing: false,
    });
  });

  it("an undelivered probe clears the wait and changes nothing else", () => {
    // The IPC failed, not the brain. Calling it down would point at the wrong machine.
    expect(linkProbeEnded({ ...down, probing: true })).toEqual(down);
  });

  it("an undelivered probe with nothing in flight is the same view", () => {
    const settled = linkProbeEnded(down);
    expect(settled).toBe(down);
  });

  it("a streamed event proves serving and drops a stale failure detail", () => {
    expect(linkServing(down)).toEqual({ state: "ready", detail: "", probing: false });
  });

  it("a streamed event keeps a detail earned while already ready, and the same view with it", () => {
    // Identity matters here: every token of every reply runs through this, and a new object
    // per token would re-render the header for nothing.
    expect(linkServing(ready)).toBe(ready);
  });

  it("a turn's transport failure is classified exactly as a probe failure would be", () => {
    const connection: TransportError = { kind: "connection", message: "refused" };
    const rpc: TransportError = { kind: "rpc", message: "Unauthenticated: bad token" };
    const protocol: TransportError = { kind: "protocol", message: "empty event" };
    expect(linkFailed(ready, connection)).toEqual({
      state: "down",
      detail: "refused",
      probing: false,
    });
    // Answered, so reachable: amber, not red. The token is wrong, the brain is not missing.
    expect(linkFailed(ready, rpc).state).toBe("degraded");
    expect(linkFailed(ready, protocol).state).toBe("degraded");
    expect(linkFailed(ready, rpc).detail).toBe("Unauthenticated: bad token");
  });

  it("a failure while a probe is out leaves the probe outstanding", () => {
    expect(linkFailed({ ...ready, probing: true }, { kind: "connection", message: "x" })).toEqual({
      state: "down",
      detail: "x",
      probing: true,
    });
  });
});

describe("describeLink", () => {
  it("reads a ready brain green, naming what answered", () => {
    expect(describeLink(ready)).toEqual({
      tone: "ok",
      busy: false,
      label: "Brain ready: cortex-orchestrator 0.1.0",
    });
  });

  it("drops the colon when there is no detail to add", () => {
    expect(describeLink(view({ state: "ready" })).label).toBe("Brain ready");
  });

  it("separates reachable-but-not-serving from unreachable", () => {
    expect(describeLink(view({ state: "degraded", detail: "store down" }))).toEqual({
      tone: "warn",
      busy: false,
      label: "The brain is not serving: store down",
    });
    expect(describeLink(down)).toEqual({
      tone: "bad",
      busy: false,
      label: "Cannot reach the brain: connection refused",
    });
  });

  it("says so plainly before the first answer", () => {
    expect(describeLink(INITIAL_LINK)).toEqual({
      tone: "idle",
      busy: false,
      label: "The brain connection has not been checked yet",
    });
  });

  it("keeps the last known colour while checking, so a reconnect neither flashes nor forgets", () => {
    expect(describeLink({ ...down, probing: true })).toEqual({
      tone: "bad",
      busy: true,
      label: "Checking the connection to the brain",
    });
    expect(describeLink({ ...INITIAL_LINK, probing: true }).tone).toBe("idle");
  });

  it("does not make a healthy link look busy for a routine refresh", () => {
    // The summon probe fires on every open. If that read as "checking", the steady state of a
    // working system would be a blinking dot.
    expect(describeLink({ ...ready, probing: true })).toEqual({
      tone: "ok",
      busy: false,
      label: "Brain ready: cortex-orchestrator 0.1.0",
    });
  });
});
