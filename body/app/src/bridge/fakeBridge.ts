import type {
  BrainBridge,
  Cancellation,
  SessionMessage,
  SessionSummary,
  TransportError,
  TurnEvent,
  TurnSink,
} from "./types";

export class FakeBridge implements BrainBridge {
  private sink: TurnSink | null = null;
  readonly calls: { readonly sessionId: string; readonly text: string }[] = [];
  /** The confirm answers sent so far, in order (ADR-0022). */
  readonly confirms: { readonly confirmId: string; readonly approved: boolean }[] = [];
  /** What `listSessions` resolves with (assignable by a test). */
  sessions: readonly SessionSummary[] = [];
  /** What `sessionMessages` resolves with, keyed by session id. */
  messagesBySession: Record<string, readonly SessionMessage[]> = {};
  /** When set, the matching read rejects (the transport-failure path). */
  listFails = false;
  messagesFail = false;
  /** When set, `respondConfirm` rejects (a lost answer, so deny-by-timeout brain-side). */
  confirmFails = false;

  converse(sessionId: string, text: string, sink: TurnSink): Cancellation {
    this.calls.push({ sessionId, text });
    this.sink = sink;
    return () => {
      this.sink = null;
    };
  }

  listSessions(_limit: number): Promise<readonly SessionSummary[]> {
    if (this.listFails) {
      return Promise.reject(new Error("list failed"));
    }
    return Promise.resolve(this.sessions);
  }

  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]> {
    if (this.messagesFail) {
      return Promise.reject(new Error("history failed"));
    }
    return Promise.resolve(this.messagesBySession[sessionId] ?? []);
  }

  respondConfirm(confirmId: string, approved: boolean): Promise<void> {
    this.confirms.push({ confirmId, approved });
    if (this.confirmFails) {
      return Promise.reject(new Error("confirm failed"));
    }
    return Promise.resolve();
  }

  /** Deliver one server event to the active turn (no-op if none). */
  emit(event: TurnEvent): void {
    this.sink?.onEvent(event);
  }

  /** Fail the active turn with a transport error (no-op if none). */
  fail(error: TransportError): void {
    this.sink?.onError(error);
  }
}
