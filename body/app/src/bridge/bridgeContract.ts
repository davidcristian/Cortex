// Shared `BrainBridge` behavior checks. Every implementation of the port must pass all of them.
//
// The TypeScript counterpart of the brain's `*_contract.py` files, `session/tests/task_contract.py`
// being the model: a flat list of named checks, each one a function over a single implementation,
// driven by one thin driver (`bridgeContract.test.ts`) parametrized over every implementation.
// Not a base class, and not a suite restated per implementation, because a restatement drifts the
// moment a check is appended to one copy and not the other (ADR-0001 addendum on decision 2).
//
// The list holds the altitude at which the implementations genuinely agree: the turn HANDLE, the
// probe, the chat catalog's reads and its three user writes, the stored history, the reminder ack,
// the settings record, and the stale confirm answer. It deliberately does not hold the CONTENT of a
// turn's stream, because the demo bridge plays a recorded conversation on a timer while the fake is
// driven by hand from the test that owns it, a divergence described in docs/modules/body-app.md.
import { expect } from "vitest";

import type { BrainBridge, LinkState, TransportError, TurnEvent, TurnSink } from "./types";

/** One implementation under the shared list, plus the two things the port itself cannot say. */
export interface BridgeCase {
  /** The implementation every check below runs against. */
  readonly bridge: BrainBridge;
  /**
   * Put a chat in this implementation's catalog, the way this implementation comes by one: the
   * demo bridge remembers a chat it was spoken in, the fake serves the table its test assigns.
   * The port has no "create a chat" call, so seeding belongs to the fixture, exactly as
   * constructing each store belongs to the fixture in the brain's contract drivers.
   */
  addChat(sessionId: string, firstMessage: string): void;
  /** Let anything this implementation paced on a timer arrive: the demo delays its answers. */
  advance(milliseconds: number): Promise<void>;
}

/** One shared check: a name (its function name, which is the test's id) and a body. */
export type BridgeCheck = (under: BridgeCase) => Promise<void>;

/** Longer than any answer either implementation paces on a timer, so awaiting one is not
 *  waiting on which implementation the check happened to be handed. */
const SETTLE_MS = 2_000;
/** Longer than a whole scripted turn, so "nothing more arrived" means the turn had its chance. */
const TURN_MS = 60_000;
/** Roomier than either catalog, so a bounded read still answers the whole listing. */
const ROOMY_LIMIT = 20;
/** A prompt that trips none of the demo bridge's scripted hooks (outage, confirm, capture). */
const PLAIN_PROMPT = "what keeps a turn's state outside the model";

/** Resolve an answer the implementation may have put on a timer. */
async function settled<T>(under: BridgeCase, pending: Promise<T>): Promise<T> {
  await under.advance(SETTLE_MS);
  return pending;
}

/** A sink that records whatever it is handed, by either door, so a check can ask what a turn
 *  delivered without first deciding which kind of thing it is asking about. The recording array's
 *  own `push` is the handler, since a check whose claim is that nothing arrived would otherwise
 *  ship a handler no run of it can ever execute. */
function recorder(): { delivered: (TurnEvent | TransportError)[]; sink: TurnSink } {
  const delivered: (TurnEvent | TransportError)[] = [];
  const record = delivered.push.bind(delivered);
  return { delivered, sink: { onEvent: record, onError: record } };
}

/** The listed ids, in listed order. */
async function listedIds(under: BridgeCase): Promise<string[]> {
  const listed = await settled(under, under.bridge.listSessions(ROOMY_LIMIT));
  return listed.map((chat) => chat.sessionId);
}

/** One chat's listed row, projected onto `field`, as a one-element array when it is listed at
 *  all: comparing the projection rather than reaching into a row keeps a missing row a failure
 *  instead of an `undefined` that quietly satisfies a "not the old title" assertion. */
async function listedField<K extends "title" | "pinned">(
  under: BridgeCase,
  sessionId: string,
  field: K,
): Promise<unknown[]> {
  const listed = await settled(under, under.bridge.listSessions(ROOMY_LIMIT));
  return listed.filter((chat) => chat.sessionId === sessionId).map((chat) => chat[field]);
}

/**
 * A turn hands back a cancellation, delivers nothing during the call, and goes silent once it
 * is cancelled, however often it is cancelled.
 *
 * Delivery lands after the call because the real bridge cannot do otherwise: its events cross a
 * Tauri channel, and every caller assigns the handle from what `converse` returned, so an event
 * raised inside the call reaches the reducer while the turn it belongs to has nothing to cancel it
 * by. The second cancellation is the overlay's own habit, cancelling on submit, on switching
 * chats, and again on unmount, so an implementation that ignored one would stream into a
 * torn-down panel.
 */
async function checkACancelledTurnGoesSilent(under: BridgeCase): Promise<void> {
  const seen = recorder();
  const cancel = under.bridge.converse("contract-turn", PLAIN_PROMPT, seen.sink);
  expect(seen.delivered).toEqual([]);
  cancel();
  cancel();
  await under.advance(TURN_MS);
  expect(seen.delivered).toEqual([]);
}

/**
 * The probe answers a classified status rather than rejecting, and answers again.
 *
 * A failed probe is an answer about the brain, not an error (ADR-0011 addendum), and the
 * indicator re-probes on a cadence, so an implementation that latched after one answer would
 * leave the dot frozen on whatever it first said.
 */
async function checkTheProbeKeepsAnsweringAStatus(under: BridgeCase): Promise<void> {
  const states: LinkState[] = ["ready", "degraded", "down"];
  const first = await settled(under, under.bridge.checkLink());
  expect(states).toContain(first.state);
  expect(typeof first.detail).toBe("string");
  const second = await settled(under, under.bridge.checkLink());
  expect(second.state).toBe(first.state);
}

/** A chat the catalog was given is listed, unpinned, under a title of its own. */
async function checkASeededChatIsListed(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  expect(await listedIds(under)).toContain("contract-a");
  expect(await listedField(under, "contract-a", "pinned")).toEqual([false]);
  const titles = await listedField(under, "contract-a", "title");
  expect(titles).toHaveLength(1);
  expect(titles[0]).not.toBe("");
}

/**
 * A zero limit means the implementation's own default listing, never an empty one.
 *
 * The port documents `0` as "the brain default" (`types.ts`), which is what the real bridge
 * forwards; an implementation reading it as "at most none" answers an empty switcher.
 */
async function checkAZeroLimitListsTheDefault(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  const bounded = await settled(under, under.bridge.listSessions(ROOMY_LIMIT));
  const defaulted = await settled(under, under.bridge.listSessions(0));
  expect(defaulted).toEqual(bounded);
}

/** A positive limit cuts the same listing rather than answering a different one. */
async function checkAPositiveLimitBoundsTheListing(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  await under.advance(SETTLE_MS);
  under.addChat("contract-b", "what does a subagent cost");
  const whole = await settled(under, under.bridge.listSessions(ROOMY_LIMIT));
  expect(whole.length).toBeGreaterThan(1);
  const cut = await settled(under, under.bridge.listSessions(1));
  expect(cut).toEqual(whole.slice(0, 1));
}

/** A rename shows in the next listing, which is what the overlay re-lists to see. */
async function checkARenameShowsInTheNextListing(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  await under.bridge.renameSession("contract-a", "Everything about model swaps");
  expect(await listedField(under, "contract-a", "title")).toEqual([
    "Everything about model swaps",
  ]);
}

/**
 * An empty title clears the override rather than storing one.
 *
 * What the row then falls back TO is each implementation's own business (the brain derives one
 * from the first message), so the shared claim is that the custom title is gone.
 */
async function checkAnEmptyRenameClearsTheCustomTitle(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  await under.bridge.renameSession("contract-a", "Everything about model swaps");
  await under.bridge.renameSession("contract-a", "");
  const titles = await listedField(under, "contract-a", "title");
  expect(titles).toHaveLength(1);
  expect(titles[0]).not.toBe("Everything about model swaps");
}

/**
 * A deleted chat is gone from the listing and stays gone on the refresh behind it.
 *
 * The overlay drops the row and immediately re-lists, so a delete that did not stick puts the
 * row back mid-exit; asking twice is what tells a real delete from an optimistic one.
 */
async function checkADeletedChatStaysGone(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  under.addChat("contract-b", "what does a subagent cost");
  await under.bridge.deleteSession("contract-a");
  const after = await listedIds(under);
  expect(after).not.toContain("contract-a");
  expect(after).toContain("contract-b");
  expect(await listedIds(under)).not.toContain("contract-a");
}

/**
 * A pinned chat lists above an unpinned one and carries the flag, and unpinning takes it back.
 *
 * The grouping is the feature (a pinned chat outlives the recency window, ADR-0021 pinning
 * addendum); where an unpinned chat sits among the others is the ordering each implementation
 * owns, so only the grouping and the flag are shared.
 */
async function checkAPinGroupsAChatAboveAnUnpinnedOne(under: BridgeCase): Promise<void> {
  under.addChat("contract-older", "how does the model swap work");
  await under.advance(TURN_MS);
  under.addChat("contract-newer", "what does a subagent cost");
  await under.bridge.setSessionPinned("contract-older", true);
  const ordered = (await listedIds(under)).filter((id) => id.startsWith("contract-"));
  expect(ordered).toEqual(["contract-older", "contract-newer"]);
  expect(await listedField(under, "contract-older", "pinned")).toEqual([true]);
  await under.bridge.setSessionPinned("contract-older", false);
  expect(await listedField(under, "contract-older", "pinned")).toEqual([false]);
}

/**
 * A chat's stored history answers well-formed messages, and a chat nobody has spoken in answers
 * rather than rejecting: an empty stage is a normal chat, not a failure the panel has to render.
 */
async function checkAHistoryAnswersRatherThanRejecting(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  const history = await settled(under, under.bridge.sessionMessages("contract-a"));
  expect(history.length).toBeGreaterThan(0);
  for (const message of history) {
    expect(["user", "assistant"]).toContain(message.role);
    expect(typeof message.text).toBe("string");
  }
  const unknown = await settled(under, under.bridge.sessionMessages("contract-never-spoken"));
  expect(Array.isArray(unknown)).toBe(true);
}

/**
 * A due reminder acks true and an id nobody was told about acks false.
 *
 * `false` is "there was nothing to clear", never a failure (`types.ts`), so an implementation
 * that answered true for an unknown id would report a delivery it never made.
 */
async function checkADueReminderAcksTrueAndAnUnknownIdFalse(under: BridgeCase): Promise<void> {
  const due = await settled(under, under.bridge.listDueReminders());
  expect(due.length).toBeGreaterThan(0);
  const ids = due.map((reminder) => reminder.reminderId);
  expect(ids).not.toContain("contract-never-fired");
  expect(await settled(under, under.bridge.ackReminder(ids[0] as string))).toBe(true);
  expect(await settled(under, under.bridge.ackReminder("contract-never-fired"))).toBe(false);
}

/**
 * A setting reads back, a second write to one key replaces it, and an empty value clears it.
 *
 * The record is the brain's (ADR-0032), so a bridge that dropped a write would hand the overlay
 * a record that never carries what the user just chose.
 */
async function checkASettingRoundTripsAndAnEmptyValueClears(under: BridgeCase): Promise<void> {
  await under.bridge.setPreference("overlay.contract", "still");
  expect(await settled(under, under.bridge.getPreferences())).toContainEqual({
    key: "overlay.contract",
    value: "still",
  });
  await under.bridge.setPreference("overlay.contract", "lucid");
  const replaced = await settled(under, under.bridge.getPreferences());
  expect(replaced.filter((pref) => pref.key === "overlay.contract")).toEqual([
    { key: "overlay.contract", value: "lucid" },
  ]);
  await under.bridge.setPreference("overlay.contract", "");
  const cleared = await settled(under, under.bridge.getPreferences());
  expect(cleared.filter((pref) => pref.key === "overlay.contract")).toEqual([]);
}

/**
 * Answering a confirmation nobody is waiting for resolves rather than rejecting.
 *
 * The card can close under the user's hand (the brain's own timeout, ADR-0022), so a click
 * landing behind it must be absorbed, and absorbed without running the gated call.
 */
async function checkAStaleConfirmAnswerIsAbsorbed(under: BridgeCase): Promise<void> {
  await expect(under.bridge.respondConfirm("contract-nobody-asked", true)).resolves.toBeUndefined();
}

/** Every check, in the order a reader meets the port: the turn, the probe, the catalog, the
 *  history, the reminders, the record, the confirm answer. */
export const ALL_CHECKS: readonly BridgeCheck[] = [
  checkACancelledTurnGoesSilent,
  checkTheProbeKeepsAnsweringAStatus,
  checkASeededChatIsListed,
  checkAZeroLimitListsTheDefault,
  checkAPositiveLimitBoundsTheListing,
  checkARenameShowsInTheNextListing,
  checkAnEmptyRenameClearsTheCustomTitle,
  checkADeletedChatStaysGone,
  checkAPinGroupsAChatAboveAnUnpinnedOne,
  checkAHistoryAnswersRatherThanRejecting,
  checkADueReminderAcksTrueAndAnUnknownIdFalse,
  checkASettingRoundTripsAndAnEmptyValueClears,
  checkAStaleConfirmAnswerIsAbsorbed,
];
