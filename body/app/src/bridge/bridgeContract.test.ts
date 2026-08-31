// One behavior suite over every `BrainBridge` implementation CI can run (ADR-0011 addendum).
//
// The driver stays thin, as the brain's `test_task_store_contract.py` does: it builds a fresh case
// per check and runs the shared list over it. Every claim lives in `bridgeContract.ts`, so a check
// appended there reaches both implementations without being written twice.
import { afterEach, beforeEach, describe, it, vi } from "vitest";

import { deriveTitle } from "../overlay/sessionState";
import { ALL_CHECKS, type BridgeCase } from "./bridgeContract";
import { DemoBridge } from "./demoBridge";
import { FakeBridge } from "./fakeBridge";
import type { TurnSink } from "./types";

/** A sink for a turn the fixture needs only the side effect of. */
const DROPPED: TurnSink = { onEvent: () => undefined, onError: () => undefined };

const advance = async (milliseconds: number): Promise<void> => {
  await vi.advanceTimersByTimeAsync(milliseconds);
};

function fakeCase(): BridgeCase {
  const bridge = new FakeBridge();
  // The fake serves the tables its test assigns, so the fixture assigns the one thing every
  // implementation is expected to have: a reminder that has fired.
  bridge.reminders = [
    {
      reminderId: "fake-r1",
      text: "stretch",
      firedAtUnixMs: Date.now(),
      recurring: false,
      tainted: false,
      sessionId: "contract-a",
    },
  ];
  return {
    bridge,
    addChat: (sessionId, firstMessage) => {
      bridge.sessions = [
        ...bridge.sessions,
        {
          sessionId,
          title: deriveTitle(firstMessage),
          preview: firstMessage,
          lastActivityUnixMs: Date.now(),
          pinned: false,
        },
      ];
      bridge.messagesBySession[sessionId] = [
        { role: "user", text: firstMessage, turnId: "t1", atUnixMs: Date.now() },
      ];
    },
    advance,
  };
}

function demoCase(): BridgeCase {
  const bridge = new DemoBridge();
  return {
    bridge,
    // The demo bridge gains a chat the way the brain does, by being spoken in. The turn is
    // cancelled immediately, since these checks are about the catalog rather than the stream.
    addChat: (sessionId, firstMessage) => bridge.converse(sessionId, firstMessage, DROPPED)(),
    advance,
  };
}

const IMPLEMENTATIONS: readonly { name: string; create: () => BridgeCase }[] = [
  { name: "FakeBridge", create: fakeCase },
  { name: "DemoBridge", create: demoCase },
];

describe.each(IMPLEMENTATIONS)("BrainBridge contract over $name", ({ create }) => {
  // Fake timers for both arms: the demo bridge paces its answers, the fake answers at once, and
  // the shared checks advance the clock through `BridgeCase.advance` either way.
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it.each(ALL_CHECKS.map((check) => [check.name, check] as const))("%s", async (_name, check) => {
    await check(create());
  });
});
