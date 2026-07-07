import type {
  BrainBridge,
  Cancellation,
  SessionMessage,
  SessionSummary,
  TransportError,
  TurnEvent,
  TurnSink,
} from "./types";

// A manually-driven fake `BrainBridge` for tests: `converse` records the call and captures the
// sink, and the test emits events/errors when it chooses, so streaming, mid-stream dismiss,
// completion, and failures are all deterministic. The session reads resolve from injectable
// tables (or reject when the failure flags are set), so the list/switcher/cycling paths are
// exercised without a server. The browser dev bridge (timer-driven, for `vite dev`) is separate
// and coverage-excluded, the frontend analog of the real Tauri bridge.
export class FakeBridge implements BrainBridge {
  private sink: TurnSink | null = null;
  readonly calls: { readonly sessionId: string; readonly text: string }[] = [];
  /** What `listSessions` resolves with (assignable by a test). */
  sessions: readonly SessionSummary[] = [];
  /** What `sessionMessages` resolves with, keyed by session id. */
  messagesBySession: Record<string, readonly SessionMessage[]> = {};
  /** When set, the matching read rejects (the transport-failure path). */
  listFails = false;
  messagesFail = false;

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

  /** Deliver one server event to the active turn (no-op if none). */
  emit(event: TurnEvent): void {
    this.sink?.onEvent(event);
  }

  /** Fail the active turn with a transport error (no-op if none). */
  fail(error: TransportError): void {
    this.sink?.onError(error);
  }
}
