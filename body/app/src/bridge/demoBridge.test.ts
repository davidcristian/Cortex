// The demo bridge's own suite: what it does BEYOND the shared `BrainBridge` list, which is the
// recorded conversation it plays and the four hooks a prompt can trip (an outage, the gated-send
// confirm round with its deadline, and the capture indicator's two rungs). The port-level claims
// it shares with the fake live in `bridgeContract.ts` and are not restated here.
//
// It runs on fake timers because the demo paces everything it says: that is the point of it in
// browser dev, and it is what makes the cadence assertable here rather than only by eye.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DemoBridge } from "./demoBridge";
import * as script from "./demoScript";
import type { TurnEvent, TurnSink } from "./types";

/** A turn under way, with everything its sink has been handed so far. */
interface Turn {
  readonly events: TurnEvent[];
  readonly cancel: () => void;
}

function speak(bridge: DemoBridge, text: string, sessionId = "demo-1"): Turn {
  const events: TurnEvent[] = [];
  const sink: TurnSink = {
    onEvent: (event) => events.push(event),
    onError: () => expect.unreachable("the demo bridge never fails a turn"),
  };
  return { events, cancel: bridge.converse(sessionId, text, sink) };
}

/** Everything the turn streamed as reply text, and everything it streamed as thinking. */
const spoken = (events: readonly TurnEvent[]): string =>
  events.flatMap((event) => (event.kind === "delta" ? [event.text] : [])).join("");
const thought = (events: readonly TurnEvent[]): string =>
  events.flatMap((event) => (event.kind === "status" ? [event.detail] : [])).join("");

/** Long enough for any scripted turn to run out of words. */
const WHOLE_TURN_MS = 30_000;

describe("DemoBridge, the recorded conversation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("thinks first, then answers, then completes exactly once", async () => {
    const bridge = new DemoBridge();
    const turn = speak(bridge, "how does the model swap work");
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(thought(turn.events)).toBe(script.REASONING);
    expect(spoken(turn.events)).toBe(script.ANSWER);
    const kinds = turn.events.map((event) => event.kind);
    // The reasoning burst is over before the reply starts, and the turn ends once, last: a
    // completion that arrived early would settle the bubble over a reply still streaming.
    expect(kinds.lastIndexOf("status")).toBeLessThan(kinds.indexOf("delta"));
    expect(kinds.filter((kind) => kind === "complete")).toEqual(["complete"]);
    expect(turn.events.at(-1)).toEqual({ kind: "complete", turnId: "demo" });
  });

  it("holds the bubble on the shimmer before the first word", async () => {
    const bridge = new DemoBridge();
    const turn = speak(bridge, "how does the model swap work");
    await vi.advanceTimersByTimeAsync(400);
    expect(turn.events).toEqual([]);
    await vi.advanceTimersByTimeAsync(200);
    expect(thought(turn.events)).not.toBe("");
  });

  it("stops mid-reply when the turn is cancelled, and says nothing after", async () => {
    const bridge = new DemoBridge();
    const turn = speak(bridge, "how does the model swap work");
    await vi.advanceTimersByTimeAsync(700);
    const interrupted = thought(turn.events);
    expect(interrupted).not.toBe("");
    turn.cancel();
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(thought(turn.events)).toBe(interrupted);
    expect(turn.events.map((event) => event.kind)).not.toContain("complete");
  });

  it("keeps one row per chat, refreshing the preview when the chat is spoken in again", async () => {
    const bridge = new DemoBridge();
    speak(bridge, "how does the model swap work", "demo-9").cancel();
    speak(bridge, "and what does a subagent cost", "demo-9").cancel();
    const listed = await bridge.listSessions(0);
    const rows = listed.filter((chat) => chat.sessionId === "demo-9");
    expect(rows.map((chat) => chat.title)).toEqual(["how does the model swap work"]);
    expect(rows.map((chat) => chat.preview)).toEqual(["and what does a subagent cost"]);
  });

  it("serves the seeded chat's own transcript, and the model-swap one for anything else", async () => {
    const bridge = new DemoBridge();
    const unread = await bridge.sessionMessages("demo-2");
    expect(unread.map((message) => message.role)).toEqual(["user", "assistant"]);
    expect(unread[0]?.text).toBe("Summarize my unread email");
    const swaps = await bridge.sessionMessages("demo-1");
    expect(swaps[1]?.text).toBe(script.ANSWER);
  });
});

describe("DemoBridge, the scripted hooks", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  /** Resolve a probe, which the demo delays so the checking pulse is visible by hand. */
  async function probe(bridge: DemoBridge): Promise<{ state: string; detail: string }> {
    const pending = bridge.checkLink();
    await vi.advanceTimersByTimeAsync(1000);
    return pending;
  }

  it("scripts an outage a prompt asks for, and heals it on its own", async () => {
    const bridge = new DemoBridge();
    speak(bridge, "pretend you are offline").cancel();
    expect(await probe(bridge)).toEqual({ state: "down", detail: script.DOWN_DETAIL });
    await vi.advanceTimersByTimeAsync(script.OUTAGE_MS);
    expect(await probe(bridge)).toEqual({ state: "ready", detail: script.READY_DETAIL });
  });

  it("scripts a degraded brain too, and a probe before the outage heals still reports it", async () => {
    const bridge = new DemoBridge();
    speak(bridge, "pretend you are degraded").cancel();
    expect(await probe(bridge)).toEqual({ state: "degraded", detail: script.DEGRADED_DETAIL });
    expect(await probe(bridge)).toEqual({ state: "degraded", detail: script.DEGRADED_DETAIL });
  });

  /** The gap between the two rungs, long enough by hand to watch the pupil grow. */
  const TO_THE_OUTCOME_MS = 450;

  it("lights the capture ring at the ask and opens its eye when the dispatch settles", async () => {
    const bridge = new DemoBridge();
    const turn = speak(bridge, "look at my screen");
    // Nothing during the call: the ask rides a timer, as it must to be something the real
    // bridge's channel could have carried.
    expect(turn.events).toEqual([]);
    await vi.advanceTimersByTimeAsync(100);
    expect(turn.events).toEqual([
      { kind: "toolActivity", toolName: "capture_screen", summary: "reading the screen" },
    ]);
    await vi.advanceTimersByTimeAsync(TO_THE_OUTCOME_MS);
    expect(turn.events[1]).toEqual({ kind: "toolOutcome", toolName: "capture_screen", ok: true });
  });

  it("settles a refused capture not-ok, so the ring holds at the ask", async () => {
    const bridge = new DemoBridge();
    const turn = speak(bridge, "look at my screen, but pretend it was refused");
    await vi.advanceTimersByTimeAsync(TO_THE_OUTCOME_MS);
    expect(turn.events[1]).toEqual({ kind: "toolOutcome", toolName: "capture_screen", ok: false });
  });

  it("leaves an asked capture unsettled when the turn is cancelled between the rungs", async () => {
    const bridge = new DemoBridge();
    const turn = speak(bridge, "look at my screen");
    await vi.advanceTimersByTimeAsync(100);
    turn.cancel();
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(turn.events.map((event) => event.kind)).toEqual(["toolActivity"]);
  });

  it("says nothing at all about a capture cancelled before it was even asked", async () => {
    const bridge = new DemoBridge();
    const turn = speak(bridge, "look at my screen");
    turn.cancel();
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(turn.events).toEqual([]);
  });
});

describe("DemoBridge, the gated send", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  /** Long enough for the preamble to run out of words, and deliberately short of the demo
   *  brain's own confirm deadline, so a turn armed with one is still waiting when this returns. */
  const TO_THE_QUESTION_MS = 2_000;

  /** Walk a send prompt up to the question it stops on. */
  async function asked(bridge: DemoBridge, text: string): Promise<Turn> {
    const turn = speak(bridge, text);
    await vi.advanceTimersByTimeAsync(TO_THE_QUESTION_MS);
    expect(turn.events.at(-1)).toEqual({
      kind: "confirmRequest",
      confirmId: "demo-confirm",
      toolName: "send_email",
      argumentsJson: script.CONFIRM_DRAFT,
      reason: script.CONFIRM_REASON,
    });
    return turn;
  }

  it("asks before sending, and finishes the reply once the send is approved", async () => {
    const bridge = new DemoBridge();
    const turn = await asked(bridge, "send that email to Ada");
    expect(spoken(turn.events)).toBe(script.CONFIRM_PREAMBLE);
    await bridge.respondConfirm("demo-confirm", true);
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(spoken(turn.events)).toBe(`${script.CONFIRM_PREAMBLE} ${script.CONFIRM_SENT}`);
    expect(turn.events.at(-1)).toEqual({ kind: "complete", turnId: "demo" });
  });

  it("says nothing was sent when the send is denied", async () => {
    const bridge = new DemoBridge();
    const turn = await asked(bridge, "send that email to Ada");
    await bridge.respondConfirm("demo-confirm", false);
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(spoken(turn.events)).toBe(`${script.CONFIRM_PREAMBLE} ${script.CONFIRM_DENIED}`);
  });

  it("stops waiting on its own deadline, and absorbs the answer that lands behind it", async () => {
    const bridge = new DemoBridge();
    const turn = await asked(bridge, "send that email to Ada, and let it time out");
    await vi.advanceTimersByTimeAsync(script.CONFIRM_TIMEOUT_MS);
    expect(turn.events).toContainEqual({
      kind: "confirmResolved",
      confirmId: "demo-confirm",
      outcome: "timeout",
    });
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    const timedOut = `${script.CONFIRM_PREAMBLE} ${script.CONFIRM_TIMED_OUT}`;
    expect(spoken(turn.events)).toBe(timedOut);
    // The card closed, so a click landing after it resumes nothing: no second reply, fail-closed.
    await bridge.respondConfirm("demo-confirm", true);
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(spoken(turn.events)).toBe(timedOut);
  });

  it("forgets the deadline when the answer beats it", async () => {
    const bridge = new DemoBridge();
    const turn = await asked(bridge, "send that email to Ada, and let it time out");
    await bridge.respondConfirm("demo-confirm", true);
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(spoken(turn.events)).toBe(`${script.CONFIRM_PREAMBLE} ${script.CONFIRM_SENT}`);
    expect(turn.events.map((event) => event.kind)).not.toContain("confirmResolved");
  });

  it("drops an open question when the turn is cancelled under it", async () => {
    const bridge = new DemoBridge();
    const turn = await asked(bridge, "send that email to Ada, and let it time out");
    turn.cancel();
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(spoken(turn.events)).toBe(script.CONFIRM_PREAMBLE);
    await bridge.respondConfirm("demo-confirm", true);
    await vi.advanceTimersByTimeAsync(WHOLE_TURN_MS);
    expect(spoken(turn.events)).toBe(script.CONFIRM_PREAMBLE);
  });

  it("clears a title back to the demo's fallback when the rename is empty", async () => {
    const bridge = new DemoBridge();
    await bridge.renameSession("demo-1", "");
    const listed = await bridge.listSessions(0);
    expect(listed.filter((chat) => chat.sessionId === "demo-1").map((chat) => chat.title)).toEqual([
      "New chat",
    ]);
  });
});
