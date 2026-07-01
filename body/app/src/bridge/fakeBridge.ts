import type { BrainBridge, Cancellation, TransportError, TurnEvent, TurnSink } from "./types";

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
