import { Channel, invoke } from "@tauri-apps/api/core";

import { toBase64 } from "./base64";
import type {
  AttachedImage,
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

// One message on a turn's IPC channel from the Rust `converse` command: exactly one of
// `event` and `error` is set.
type WireMessage = { readonly event: TurnEvent } | { readonly error: TransportError };

/** The real `BrainBridge`: each `converse` opens a Tauri IPC `Channel`, hands it to the Rust
 *  `converse` command, and forwards streamed messages to the sink. Excluded from coverage and
 *  checked on the host, like the Rust OS adapters. */
export class TauriBridge implements BrainBridge {
  converse(
    sessionId: string,
    text: string,
    images: readonly AttachedImage[],
    sink: TurnSink,
  ): Cancellation {
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
    // IPC arguments are JSON, so the bytes cross as base64 (`WireImage` in converse.rs).
    const wire = images.map(({ data, mimeType, width, height }) => ({
      dataBase64: toBase64(data),
      mimeType,
      width,
      height,
    }));
    invoke("converse", { sessionId, text, images: wire, channel }).catch((reason: unknown) => {
      if (live) {
        sink.onError({ kind: "connection", message: String(reason) });
      }
    });
    // Cancelling only stops delivery to the sink. The Rust command streams the turn to its end,
    // so the brain finishes it and stores it.
    return () => {
      live = false;
    };
  }

  // The Rust command never rejects: an unreachable brain comes back as `{ state: "down", detail, notes: [] }`.
  checkLink(): Promise<LinkStatus> {
    return invoke<LinkStatus>("check_link");
  }

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

  setSessionHoisted(sessionId: string, hoisted: boolean): Promise<void> {
    return invoke<void>("set_session_hoisted", { sessionId, hoisted });
  }

  listDueReminders(): Promise<readonly DueReminder[]> {
    return invoke<readonly DueReminder[]>("list_due_reminders");
  }

  ackReminder(reminderId: string, firedAtUnixMs: number): Promise<boolean> {
    return invoke<boolean>("ack_reminder", { reminderId, firedAtUnixMs });
  }

  // The Rust side returns the pairs as tuples, the one difference from the port, mapped here.
  getPreferences(): Promise<readonly Preference[]> {
    return invoke<readonly [string, string][]>("get_preferences").then((pairs) =>
      pairs.map(([key, value]) => ({ key, value })),
    );
  }

  setPreference(key: string, value: string): Promise<void> {
    return invoke<void>("set_preference", { key, value });
  }

  // A failure here is not fatal for the caller, because the brain denies by timeout.
  respondConfirm(confirmId: string, approved: boolean): Promise<void> {
    return invoke<void>("confirm_response", { confirmId, approved });
  }
}
