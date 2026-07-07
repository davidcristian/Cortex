import { Channel, invoke } from "@tauri-apps/api/core";

import type {
  BrainBridge,
  Cancellation,
  SessionMessage,
  SessionSummary,
  TransportError,
  TurnEvent,
  TurnSink,
} from "./types";

// One message on a turn's IPC channel from the Rust `converse` command: exactly
// one of `event`/`error` is set (mirrors the Rust `WireMessage`; ADR-0011).
type WireMessage = { readonly event: TurnEvent } | { readonly error: TransportError };

/**
 * The real `BrainBridge`: each `converse` opens a Tauri IPC `Channel`, hands it
 * to the Rust `converse` command, and forwards streamed messages to the sink.
 *
 * Coverage-excluded as the frontend analog of the Rust host adapters, validated on
 * the host (Tauri), never in CI. All branchy turn logic lives in the gated core
 * (`overlayState`, `useOverlay`); this is thin wiring.
 */
export class TauriBridge implements BrainBridge {
  converse(sessionId: string, text: string, sink: TurnSink): Cancellation {
    const channel = new Channel<WireMessage>();
    let live = true;
    channel.onmessage = (message) => {
      if (!live) {
        return;
      }
      if ("event" in message) {
        sink.onEvent(message.event);
      } else {
        sink.onError(message.error);
      }
    };
    invoke("converse", { sessionId, text, channel }).catch((reason: unknown) => {
      if (live) {
        sink.onError({ kind: "connection", message: String(reason) });
      }
    });
    // Cancellation stops delivery to the sink; dropping the channel on the Rust
    // side half-closes the Converse RPC (drop-to-cancel, ADR-0011).
    return () => {
      live = false;
    };
  }

  // The read-only session views (ADR-0021): simple request/response Tauri commands
  // that call the brain's ListSessions / GetSessionMessages over the seam.
  listSessions(limit: number): Promise<readonly SessionSummary[]> {
    return invoke<readonly SessionSummary[]>("list_sessions", { limit });
  }

  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]> {
    return invoke<readonly SessionMessage[]>("session_messages", { sessionId });
  }
}
