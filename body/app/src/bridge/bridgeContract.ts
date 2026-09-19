// The shared behavior checks every `BrainBridge` implementation must pass. They do not cover the
// content of a turn's stream: the demo bridge plays a recorded conversation on a timer, while the
// fake is driven by hand from the test that owns it.
import { expect } from "vitest";

import type { BrainBridge, LinkState, TransportError, TurnEvent, TurnSink } from "./types";

/** One implementation to check, plus the two things the port itself cannot do. */
export interface BridgeCase {
  readonly bridge: BrainBridge;
  /** Add a chat by whatever route this implementation has: the demo bridge remembers a chat it
   *  was spoken in, the fake serves the table its test assigns. */
  addChat(sessionId: string, firstMessage: string): void;
  /** Let through anything the implementation put on a timer; the demo delays its answers. */
  advance(milliseconds: number): Promise<void>;
}

/** One shared check. Its function name is the test's id. */
export type BridgeCheck = (under: BridgeCase) => Promise<void>;

/** Longer than any answer either implementation puts on a timer. */
const SETTLE_MS = 2_000;
/** Longer than a whole scripted turn, so "nothing more arrived" is a real result. */
const TURN_MS = 60_000;
/** Larger than either chat list, so a bounded read still returns the whole listing. */
const ROOMY_LIMIT = 20;
/** A prompt that triggers none of the demo bridge's scripted events (outage, confirm, capture). */
const PLAIN_PROMPT = "what keeps a turn's state outside the model";

/** Resolve an answer the implementation may have put on a timer. */
async function settled<T>(under: BridgeCase, pending: Promise<T>): Promise<T> {
  await under.advance(SETTLE_MS);
  return pending;
}

/** A sink that records events and errors into one array, so a check can ask what a turn
 *  delivered without reading two channels. */
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

/** One chat's listed row projected onto `field`, as a one-element array. Projecting rather than
 *  indexing keeps a missing row a failure, where indexing would return `undefined`. */
async function listedField<K extends "title" | "pinned">(
  under: BridgeCase,
  sessionId: string,
  field: K,
): Promise<unknown[]> {
  const listed = await settled(under, under.bridge.listSessions(ROOMY_LIMIT));
  return listed.filter((chat) => chat.sessionId === sessionId).map((chat) => chat[field]);
}

/** Cancelling twice is safe, and nothing is delivered during the `converse` call itself. */
async function checkACancelledTurnGoesSilent(under: BridgeCase): Promise<void> {
  const seen = recorder();
  const cancel = under.bridge.converse("contract-turn", PLAIN_PROMPT, seen.sink);
  expect(seen.delivered).toEqual([]);
  cancel();
  cancel();
  await under.advance(TURN_MS);
  expect(seen.delivered).toEqual([]);
}

async function checkTheProbeKeepsAnsweringAStatus(under: BridgeCase): Promise<void> {
  const states: LinkState[] = ["ready", "degraded", "down"];
  const first = await settled(under, under.bridge.checkLink());
  expect(states).toContain(first.state);
  expect(typeof first.detail).toBe("string");
  const second = await settled(under, under.bridge.checkLink());
  expect(second.state).toBe(first.state);
}

/** The new chat is listed, not `pinned`, and has a title of its own. */
async function checkASeededChatIsListed(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  expect(await listedIds(under)).toContain("contract-a");
  expect(await listedField(under, "contract-a", "pinned")).toEqual([false]);
  const titles = await listedField(under, "contract-a", "title");
  expect(titles).toHaveLength(1);
  expect(titles[0]).not.toBe("");
}

async function checkAZeroLimitListsTheDefault(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  const bounded = await settled(under, under.bridge.listSessions(ROOMY_LIMIT));
  const defaulted = await settled(under, under.bridge.listSessions(0));
  expect(defaulted).toEqual(bounded);
}

async function checkAPositiveLimitBoundsTheListing(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  await under.advance(SETTLE_MS);
  under.addChat("contract-b", "what does a subagent cost");
  const whole = await settled(under, under.bridge.listSessions(ROOMY_LIMIT));
  expect(whole.length).toBeGreaterThan(1);
  const cut = await settled(under, under.bridge.listSessions(1));
  expect(cut).toEqual(whole.slice(0, 1));
}

async function checkARenameShowsInTheNextListing(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  await under.bridge.renameSession("contract-a", "Everything about model swaps");
  expect(await listedField(under, "contract-a", "title")).toEqual([
    "Everything about model swaps",
  ]);
}

async function checkAnEmptyRenameClearsTheCustomTitle(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  await under.bridge.renameSession("contract-a", "Everything about model swaps");
  await under.bridge.renameSession("contract-a", "");
  const titles = await listedField(under, "contract-a", "title");
  expect(titles).toHaveLength(1);
  expect(titles[0]).not.toBe("Everything about model swaps");
}

/** The list is read twice, because the overlay drops the row and then re-lists. */
async function checkADeletedChatStaysGone(under: BridgeCase): Promise<void> {
  under.addChat("contract-a", "how does the model swap work");
  under.addChat("contract-b", "what does a subagent cost");
  await under.bridge.deleteSession("contract-a");
  const after = await listedIds(under);
  expect(after).not.toContain("contract-a");
  expect(after).toContain("contract-b");
  expect(await listedIds(under)).not.toContain("contract-a");
}

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

/** A chat nobody has spoken in returns an empty list: an empty chat is normal, not a failure. */
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

async function checkADueReminderAcksTrueAndAnUnknownIdFalse(under: BridgeCase): Promise<void> {
  const due = await settled(under, under.bridge.listDueReminders());
  expect(due.length).toBeGreaterThan(0);
  const first = due[0] as (typeof due)[number];
  expect(due.map((reminder) => reminder.reminderId)).not.toContain("contract-never-fired");
  const earlier = first.firedAtUnixMs - 1;
  expect(await settled(under, under.bridge.ackReminder(first.reminderId, earlier))).toBe(false);
  const { reminderId, firedAtUnixMs } = first;
  expect(await settled(under, under.bridge.ackReminder(reminderId, firedAtUnixMs))).toBe(true);
  const unknown = under.bridge.ackReminder("contract-never-fired", firedAtUnixMs);
  expect(await settled(under, unknown)).toBe(false);
}

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

/** The card can close before the click arrives, so a late answer resolves instead of failing. */
async function checkAStaleConfirmAnswerIsAbsorbed(under: BridgeCase): Promise<void> {
  await expect(under.bridge.respondConfirm("contract-nobody-asked", true)).resolves.toBeUndefined();
}

/** Every check, in the order a reader meets the port. */
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
