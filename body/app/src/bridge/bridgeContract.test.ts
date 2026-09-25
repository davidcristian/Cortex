import { afterEach, beforeEach, describe, it, vi } from "vitest";

import { deriveTitle } from "../overlay/sessionState";
import { ALL_CHECKS, type BridgeCase } from "./bridgeContract";
import { DemoBridge } from "./demoBridge";
import { FakeBridge } from "./fakeBridge";
import type { TurnSink } from "./types";

/** A sink for a turn the fixture starts only for its side effect. */
const DROPPED: TurnSink = { onEvent: () => undefined, onError: () => undefined };

const advance = async (milliseconds: number): Promise<void> => {
  await vi.advanceTimersByTimeAsync(milliseconds);
};

function fakeCase(): BridgeCase {
  const bridge = new FakeBridge();
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
          hoisted: false,
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
    // The demo bridge only learns about a chat by being spoken in. The turn is cancelled right
    // away, because these checks are about the chat list rather than the stream.
    addChat: (sessionId, firstMessage) => bridge.converse(sessionId, firstMessage, [], DROPPED)(),
    advance,
  };
}

const IMPLEMENTATIONS: readonly { name: string; create: () => BridgeCase }[] = [
  { name: "FakeBridge", create: fakeCase },
  { name: "DemoBridge", create: demoCase },
];

describe.each(IMPLEMENTATIONS)("BrainBridge contract over $name", ({ create }) => {
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
