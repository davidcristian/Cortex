// Typed mirror of the Rust `body_core::TurnEvent` / `TransportError`, plus the
// `BrainBridge` port the overlay depends on (ADR-0011). The real Tauri-backed
// implementation lives in `bridge/tauriBridge.ts` (the one un-gated glue
// module); a fake drives tests and browser dev.

export type TurnEvent =
  | { readonly kind: "delta"; readonly text: string }
  | { readonly kind: "toolActivity"; readonly toolName: string; readonly summary: string }
  /**
   * How a dispatch the `toolActivity` above announced ENDED (ADR-0029 outcome addendum). The
   * brain emits exactly one per activity on the turn's own stream, on every path out of the
   * dispatch, so a surface lit by an activity has something honest to settle it with.
   *
   * It exists for the screen-capture indicator, which is a consent surface. **It may only ever
   * strengthen what that surface claims, never retract it:** `ok: false` means the brain cannot
   * say the tool reached anything, never that nothing happened, because a capture that failed
   * after the shutter fired looks identical from this side.
   */
  | { readonly kind: "toolOutcome"; readonly toolName: string; readonly ok: boolean }
  | { readonly kind: "status"; readonly state: string; readonly detail: string }
  | {
      readonly kind: "confirmRequest";
      readonly confirmId: string;
      readonly toolName: string;
      readonly argumentsJson: string;
      readonly reason: string;
    }
  /**
   * A `confirmRequest` the brain stopped waiting on (ADR-0022), so the card can close
   * before it becomes a lie. Only arrives for endings this side cannot see: the brain's
   * confirm timeout, and its input stream ending. The user's own answer is never echoed,
   * and a dying turn is closed by its terminal event instead. `outcome` ("timeout" |
   * "unavailable") explains and never authorizes: none of them ran the gated call.
   */
  | { readonly kind: "confirmResolved"; readonly confirmId: string; readonly outcome: string }
  | { readonly kind: "complete"; readonly turnId: string }
  | { readonly kind: "failed"; readonly code: string; readonly message: string };

export type TransportErrorKind = "connection" | "rpc" | "protocol" | "timeout";

export interface TransportError {
  readonly kind: TransportErrorKind;
  readonly message: string;
}

/** Receives the streamed events of one `Converse` turn. */
export interface TurnSink {
  onEvent(event: TurnEvent): void;
  onError(error: TransportError): void;
}

/** Cancels an in-flight turn (drops the stream). */
export type Cancellation = () => void;

/** One recent chat as the switcher shows it (mirror of the proto `SessionSummary`, ADR-0021). */
export interface SessionSummary {
  readonly sessionId: string;
  readonly title: string;
  readonly preview: string;
  readonly lastActivityUnixMs: number;
  /**
   * Whether the user pinned this chat (ADR-0021 pinning addendum). The brain unions pinned chats
   * into the listing regardless of recency and sorts them above the recency group, so the switcher
   * receives them already grouped first and only has to render the pin indicator per row.
   */
  readonly pinned: boolean;
}

/** One persisted message in a session's history (mirror of the proto `SessionMessage`). */
export interface SessionMessage {
  readonly role: "user" | "assistant";
  readonly text: string;
  readonly turnId: string;
  readonly atUnixMs: number;
}

/**
 * One fired-but-undelivered reminder (mirror of the proto `DueReminder`, ADR-0025).
 * `text` is display-only and never linkified: it is the one string the overlay shows
 * that no output guardrail has inspected (ADR-0015 filters replies, not store rows).
 */
export interface DueReminder {
  readonly reminderId: string;
  readonly text: string;
  /** When it became deliverable, for the card's relative timestamp. */
  readonly firedAtUnixMs: number;
  /** Whether the series re-arms, so dismissing reads as "this one", not "cancel it". */
  readonly recurring: boolean;
  /** Untrusted provenance: the card badges it (ADR-0013/0025). */
  readonly tainted: boolean;
  /** The origin chat, or "" for a session-less caller. */
  readonly sessionId: string;
}

/**
 * What the last seam answer proved about the brain (mirror of the Rust `body_core::LinkState`,
 * ADR-0011 addendum): `ready` = it answered and reports itself serving, `degraded` = it answered
 * and is not serving (not ready, a non-OK status, an unreadable reply), `down` = it could not be
 * reached at all. The overlay adds its own `unknown` for "not asked yet"; the seam never does,
 * because every probe answers.
 */
export type LinkState = "ready" | "degraded" | "down";

/** One classified seam answer: the state plus a display-only line of detail (never parsed). */
export interface LinkStatus {
  readonly state: LinkState;
  readonly detail: string;
}

/** One stored setting (mirror of the proto `Preference`, ADR-0032). Values are opaque strings:
 *  the brain never parses one, and the overlay parses only the keys it owns. */
export interface Preference {
  readonly key: string;
  readonly value: string;
}

/** The overlay's port to the brain. Implemented over Tauri IPC (real) or a fake. */
export interface BrainBridge {
  converse(sessionId: string, text: string, sink: TurnSink): Cancellation;
  /**
   * Probe the seam once for the connection indicator. Resolves with a state even when the
   * brain is unreachable: a failed probe is an answer about the brain, not an error. The
   * probe rides the resilient transport, so it is also the reconnect attempt (ADR-0024).
   */
  checkLink(): Promise<LinkStatus>;
  /** Recent chats, newest-active first (at most `limit`; `0` = the brain default). */
  listSessions(limit: number): Promise<readonly SessionSummary[]>;
  /** One session's persisted history, in append order. */
  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]>;
  /**
   * Rename one chat (`BrainService.RenameSession`, ADR-0021 management addendum): the user's
   * own relabel from the switcher. `title` is the new display label; `""` clears any custom
   * title so the row falls back to its derived one. A user-only write (no model, tool, or
   * tainted turn reaches it) and not retried, so a lost answer surfaces rather than re-labelling.
   * The overlay re-lists after it resolves to show the change.
   */
  renameSession(sessionId: string, title: string): Promise<void>;
  /**
   * Delete one chat (`BrainService.DeleteSession`, ADR-0021 management addendum): the user's own
   * destructive removal from the switcher, fired only after an overlay-local "are you sure" confirm.
   * The brain hard-deletes the transcript and cascades to the chat's private memories. A user-only
   * write (no model, tool, or tainted turn reaches it) and NOT retried, so a lost answer surfaces
   * rather than silently re-issuing a destroy. The overlay drops the row and re-lists on success.
   */
  deleteSession(sessionId: string): Promise<void>;
  /**
   * Pin or unpin one chat (`BrainService.SetSessionPinned`, ADR-0021 pinning addendum): the user's
   * own pin toggle from the switcher. `pinned` is the target state. The brain unions a pinned chat
   * into the listing regardless of recency, so pinning keeps an important chat reachable after it
   * ages out of the recency window. A user-only write (no model, tool, or tainted turn reaches it)
   * and NOT retried, so a lost answer surfaces rather than re-asserting a stale pin. The overlay
   * re-lists after it resolves to reflect the new grouping.
   */
  setSessionPinned(sessionId: string, pinned: boolean): Promise<void>;
  /** Reminders that have fired and still await delivery, across every session (ADR-0025). */
  listDueReminders(): Promise<readonly DueReminder[]>;
  /**
   * Mark one reminder delivered. `false` is the brain reporting there was nothing to
   * clear (unknown or already acked), not a failure. Unretried by design: a lost ack
   * re-surfaces the reminder on the next open rather than risking a misread answer.
   */
  ackReminder(reminderId: string): Promise<boolean>;
  /**
   * Answer a mid-turn `confirmRequest` (ADR-0022). A failure is non-fatal: an
   * unanswered confirmation denies by timeout brain-side (fail-closed).
   */
  respondConfirm(confirmId: string, approved: boolean): Promise<void>;
  /**
   * The user's settings record, read whole (`BrainService.GetPreferences`, ADR-0032). The
   * overlay asks once at startup and applies the keys it knows; an unrecognised key belongs to
   * some other surface and is ignored, never an error. An empty record is the normal first run.
   */
  getPreferences(): Promise<readonly Preference[]>;
  /**
   * Write one setting (`BrainService.SetPreference`, ADR-0032). An empty `value` CLEARS the key,
   * so the reader's own default applies again. A user-only write and not retried; a failure is
   * non-fatal, because the choice is already applied in this session and only its durability is
   * lost.
   */
  setPreference(key: string, value: string): Promise<void>;
}
