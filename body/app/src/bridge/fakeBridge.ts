import type { BrainBridge, Cancellation, TransportError, TurnEvent, TurnSink } from "./types";

// A manually-driven fake `BrainBridge` for tests: `converse` records the call and captures the
// sink, and the test emits events/errors when it chooses, so streaming, mid-stream dismiss,
// completion, and failures are all deterministic. The browser dev bridge (timer-driven, for
// `vite dev`) is separate and coverage-excluded, the frontend analog of the real Tauri bridge.
export class FakeBridge implements BrainBridge {
  private sink: TurnSink | null = null;
  readonly calls: { readonly sessionId: string; readonly text: string }[] = [];

  converse(sessionId: string, text: string, sink: TurnSink): Cancellation {
    this.calls.push({ sessionId, text });
    this.sink = sink;
    return () => {
      this.sink = null;
    };
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
