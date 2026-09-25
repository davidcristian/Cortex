// The turn events and the `BrainBridge` port the overlay uses, mirroring the Rust `body_core`
// types of the same names.

export type TurnEvent =
  | { readonly kind: "delta"; readonly text: string }
  | { readonly kind: "toolActivity"; readonly toolName: string; readonly summary: string }
  /**
   * How the tool call that `toolActivity` announced ended. `ok: false` means the brain cannot
   * confirm the tool reached anything, not that nothing happened: a screen capture that failed
   * after the screen was read looks the same from here.
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
  /** A `confirmRequest` the brain stopped waiting on, so the card can close. `outcome` is
   *  "timeout" or "unavailable"; neither one ran the tool. */
  | { readonly kind: "confirmResolved"; readonly confirmId: string; readonly outcome: string }
  /** The turn still runs, sent while it is otherwise quiet. `wait` is the `status` state it
   *  waits on, or "" for none, and `detail` is the sentence to show for it. */
  | { readonly kind: "heartbeat"; readonly wait: string; readonly detail: string }
  | { readonly kind: "complete"; readonly turnId: string }
  | { readonly kind: "failed"; readonly code: string; readonly message: string };

export type TransportErrorKind = "connection" | "rpc" | "protocol" | "timeout";

export interface TransportError {
  readonly kind: TransportErrorKind;
  readonly message: string;
}

/** A picture the user attached to a turn, already decoded, downscaled and encoded again. */
export interface AttachedImage {
  readonly data: Uint8Array;
  /** `image/png`, `image/jpeg` or `image/webp`; the brain checks it against the first bytes. */
  readonly mimeType: string;
  readonly width: number;
  readonly height: number;
}

/** Receives the streamed events of one `Converse` turn. */
export interface TurnSink {
  onEvent(event: TurnEvent): void;
  onError(error: TransportError): void;
}

/** Cancels an in-flight turn (drops the stream). */
export type Cancellation = () => void;

/** One recent chat as the switcher shows it (mirror of the proto `SessionSummary`). */
export interface SessionSummary {
  readonly sessionId: string;
  readonly title: string;
  readonly preview: string;
  readonly lastActivityUnixMs: number;
  /** Whether the user has hoisted this chat. The brain lists those first, whatever their age. */
  readonly hoisted: boolean;
}

/** One persisted message in a session's history (mirror of the proto `SessionMessage`). */
export interface SessionMessage {
  readonly role: "user" | "assistant";
  readonly text: string;
  readonly turnId: string;
  readonly atUnixMs: number;
}

/** One reminder that has fired and has not been delivered yet. `text` is shown as plain text and
 *  never turned into links: no output filter has inspected it. */
export interface DueReminder {
  readonly reminderId: string;
  readonly text: string;
  /** When it became deliverable, for the card's relative timestamp. */
  readonly firedAtUnixMs: number;
  /** Whether the reminder repeats, so dismissing it clears this one fire, not the series. */
  readonly recurring: boolean;
  /** Whether the text came from an untrusted source; the card shows a badge for it. */
  readonly tainted: boolean;
  /** The chat it came from, or "" when the caller had no session. */
  readonly sessionId: string;
}

/** What the last probe found: `ready` = the brain answered and reports itself serving,
 *  `degraded` = it answered but is not serving, `down` = it could not be reached. The overlay
 *  adds its own `unknown` for "not asked yet". */
export type LinkState = "ready" | "degraded" | "down";

/** One classified answer from the brain: a state plus a line of detail for display only. */
export interface LinkStatus {
  readonly state: LinkState;
  readonly detail: string;
  /** A ready brain's notes, one fact each; `detail` joins the same notes into one line. */
  readonly notes: readonly string[];
}

/** One stored setting (mirror of the proto `Preference`). Values are opaque strings that the
 *  brain never parses. */
export interface Preference {
  readonly key: string;
  readonly value: string;
}

/** The overlay's port to the brain, implemented over Tauri IPC or by a fake. */
export interface BrainBridge {
  converse(
    sessionId: string,
    text: string,
    images: readonly AttachedImage[],
    sink: TurnSink,
  ): Cancellation;
  /** Probe the brain once for the connection indicator. Resolves with a state even when the
   *  brain is unreachable: a failed probe is an answer about it, not an error. */
  checkLink(): Promise<LinkStatus>;
  /** Recent chats, newest-active first (at most `limit`; `0` = the brain default). */
  listSessions(limit: number): Promise<readonly SessionSummary[]>;
  /** One session's persisted history, in append order. */
  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]>;
  /** Rename one chat. An empty `title` clears the custom title, so the row falls back to the
   *  one the brain derives. */
  renameSession(sessionId: string, title: string): Promise<void>;
  /** Delete one chat and the memories private to it. Not retried, so a lost answer shows as a
   *  failure instead of repeating the delete. */
  deleteSession(sessionId: string): Promise<void>;
  /** Set whether the brain lists this chat regardless of how old it is. */
  setSessionHoisted(sessionId: string, hoisted: boolean): Promise<void>;
  /** Reminders that have fired and still await delivery, across every session. */
  listDueReminders(): Promise<readonly DueReminder[]>;
  /** Mark the fire a card showed as delivered, named by its `firedAtUnixMs`, so dismissing a card
   *  that a later fire has replaced clears nothing and the later fire shows on the next open.
   *  `false` means there was nothing to clear, not a failure. */
  ackReminder(reminderId: string, firedAtUnixMs: number): Promise<boolean>;
  /** Answer a mid-turn `confirmRequest`. A failure is not fatal: an unanswered confirmation is
   *  denied by the brain's own timeout. */
  respondConfirm(confirmId: string, approved: boolean): Promise<void>;
  /** The user's settings record, read whole. A key the overlay does not recognise belongs to
   *  something else and is ignored. */
  getPreferences(): Promise<readonly Preference[]>;
  /** Write one setting. An empty `value` clears the key, so the reader's own default applies. */
  setPreference(key: string, value: string): Promise<void>;
}
