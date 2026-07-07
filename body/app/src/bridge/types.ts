// Typed mirror of the Rust `body_core::TurnEvent` / `TransportError`, plus the
// `BrainBridge` port the overlay depends on (ADR-0011). The real Tauri-backed
// implementation lives in `bridge/tauriBridge.ts` (the one un-gated glue
// module); a fake drives tests and browser dev.

export type TurnEvent =
  | { readonly kind: "delta"; readonly text: string }
  | { readonly kind: "toolActivity"; readonly toolName: string; readonly summary: string }
  | { readonly kind: "status"; readonly state: string; readonly detail: string }
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

/** The overlay's port to the brain. Implemented over Tauri IPC (real) or a fake. */
export interface BrainBridge {
  converse(sessionId: string, text: string, sink: TurnSink): Cancellation;
  /** Recent chats, newest-active first (at most `limit`; `0` = the brain default). */
  listSessions(limit: number): Promise<readonly SessionSummary[]>;
  /** One session's persisted history, in append order. */
  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]>;
}
