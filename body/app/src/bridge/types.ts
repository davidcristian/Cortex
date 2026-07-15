// Typed mirror of the Rust `body_core::TurnEvent` / `TransportError`, plus the
// `BrainBridge` port the overlay depends on (ADR-0011). The real Tauri-backed
// implementation lives in `bridge/tauriBridge.ts` (the one un-gated glue
// module); a fake drives tests and browser dev.

export type TurnEvent =
  | { readonly kind: "delta"; readonly text: string }
  | { readonly kind: "toolActivity"; readonly toolName: string; readonly summary: string }
  | { readonly kind: "status"; readonly state: string; readonly detail: string }
  | {
      readonly kind: "confirmRequest";
      readonly confirmId: string;
      readonly toolName: string;
      readonly argumentsJson: string;
      readonly reason: string;
    }
  | { readonly kind: "complete"; readonly turnId: string }
  | { readonly kind: "failed"; readonly code: string; readonly message: string };

export type TransportErrorKind = "connection" | "rpc" | "protocol";

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

/** The overlay's port to the brain. Implemented over Tauri IPC (real) or a fake. */
export interface BrainBridge {
  converse(sessionId: string, text: string, sink: TurnSink): Cancellation;
  /** Recent chats, newest-active first (at most `limit`; `0` = the brain default). */
  listSessions(limit: number): Promise<readonly SessionSummary[]>;
  /** One session's persisted history, in append order. */
  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]>;
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
}
