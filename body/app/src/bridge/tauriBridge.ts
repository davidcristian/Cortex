import { Channel, invoke } from "@tauri-apps/api/core";

import type {
  BrainBridge,
  Cancellation,
  DueReminder,
  LinkStatus,
  Preference,
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

  // The connection probe (ADR-0011 addendum). The Rust command is infallible: an unreachable
  // brain comes back as `{ state: "down", detail }`, not as a rejected promise, so the overlay
  // never has to guess what a rejection meant.
  checkLink(): Promise<LinkStatus> {
    return invoke<LinkStatus>("check_link");
  }

  // The read-only session views (ADR-0021): simple request/response Tauri commands
  // that call the brain's ListSessions / GetSessionMessages over the seam.
  listSessions(limit: number): Promise<readonly SessionSummary[]> {
    return invoke<readonly SessionSummary[]>("list_sessions", { limit });
  }

  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]> {
    return invoke<readonly SessionMessage[]>("session_messages", { sessionId });
  }

  renameSession(sessionId: string, title: string): Promise<void> {
    return invoke<void>("rename_session", { sessionId, title });
  }

  deleteSession(sessionId: string): Promise<void> {
    return invoke<void>("delete_session", { sessionId });
  }

  setSessionPinned(sessionId: string, pinned: boolean): Promise<void> {
    return invoke<void>("set_session_pinned", { sessionId, pinned });
  }

  // Reminder pull delivery (ADR-0025): the overlay reads what has fired when it opens and
  // acks what the user dismisses. Both are unary commands over the same resilient transport.
  listDueReminders(): Promise<readonly DueReminder[]> {
    return invoke<readonly DueReminder[]>("list_due_reminders");
  }

  ackReminder(reminderId: string): Promise<boolean> {
    return invoke<boolean>("ack_reminder", { reminderId });
  }

  // The user's settings record (ADR-0032). The Rust side answers pairs as tuples, which is the
  // one shape difference from the port, so it is mapped here rather than leaking into the app.
  getPreferences(): Promise<readonly Preference[]> {
    return invoke<readonly [string, string][]>("get_preferences").then((pairs) =>
      pairs.map(([key, value]) => ({ key, value })),
    );
  }

  setPreference(key: string, value: string): Promise<void> {
    return invoke<void>("set_preference", { key, value });
  }

  // The confirm answer (ADR-0022): a fire-and-forget command that pushes the decision
  // into the open turn's held sender. Failures are the caller's non-fatal `.catch`, since
  // the brain denies by timeout (fail-closed).
  respondConfirm(confirmId: string, approved: boolean): Promise<void> {
    return invoke<void>("confirm_response", { confirmId, approved });
  }
}
