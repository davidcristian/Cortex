import type {
  BrainBridge,
  Cancellation,
  DueReminder,
  LinkStatus,
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
  /** Session ids `sessionMessages` was asked for, in order (proves the adopt latch fires once). */
  readonly messagesCalls: string[] = [];
  /** The confirm answers sent so far, in order (ADR-0022). */
  readonly confirms: { readonly confirmId: string; readonly approved: boolean }[] = [];
  /** What `listSessions` resolves with (assignable by a test). */
  sessions: readonly SessionSummary[] = [];
  /** How many times the chat list was read (proves the mount, turn, and summon triggers). */
  listCalls = 0;
  /** What `sessionMessages` resolves with, keyed by session id. */
  messagesBySession: Record<string, readonly SessionMessage[]> = {};
  /** Rename writes received, in order (session id + new title), proving the args crossed. */
  readonly renames: { readonly sessionId: string; readonly title: string }[] = [];
  /** When set, the matching read rejects (the transport-failure path). */
  listFails = false;
  messagesFail = false;
  /** When set, `renameSession` rejects (a lost write, so the list is left unrelabelled). */
  renameFails = false;
  /** When set, `respondConfirm` rejects (a lost answer, so deny-by-timeout brain-side). */
  confirmFails = false;
  /** What `listDueReminders` resolves with (assignable by a test; ADR-0025). */
  reminders: readonly DueReminder[] = [];
  /** How many times the overlay pulled the due list (proves the open latch fires once). */
  reminderListCalls = 0;
  /** Reminder ids acked so far, in order. */
  readonly acks: string[] = [];
  /** When set, the matching reminder call rejects (an unreachable brain). */
  remindersFail = false;
  ackFails = false;
  /** What `checkLink` resolves with (assignable by a test; ADR-0011 addendum). */
  link: LinkStatus = { state: "ready", detail: "fake brain" };
  /** How many probes the overlay has fired (proves the summon latch + recovery cadence). */
  linkCalls = 0;
  /** When set, `checkLink` rejects: the IPC failed, which says nothing about the brain. */
  linkFails = false;
  /** When set, `checkLink` never settles, so a test can hold a probe in flight. */
  linkHangs = false;

  converse(sessionId: string, text: string, sink: TurnSink): Cancellation {
    this.calls.push({ sessionId, text });
    this.sink = sink;
    return () => {
      this.sink = null;
    };
  }

  // The real command answers a state even for an unreachable brain, so the fake's default is a
  // resolved status; `linkFails` is the narrower case of the IPC itself failing.
  checkLink(): Promise<LinkStatus> {
    this.linkCalls += 1;
    if (this.linkHangs) {
      return new Promise<LinkStatus>(() => undefined);
    }
    if (this.linkFails) {
      return Promise.reject(new Error("probe failed"));
    }
    return Promise.resolve(this.link);
  }

  listSessions(_limit: number): Promise<readonly SessionSummary[]> {
    this.listCalls += 1;
    if (this.listFails) {
      return Promise.reject(new Error("list failed"));
    }
    return Promise.resolve(this.sessions);
  }

  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]> {
    this.messagesCalls.push(sessionId);
    if (this.messagesFail) {
      return Promise.reject(new Error("history failed"));
    }
    return Promise.resolve(this.messagesBySession[sessionId] ?? []);
  }

  // Records the write and, on success, reflects it in the injectable list so a subsequent
  // re-list shows the new label exactly as the brain's `set_title` would (ADR-0021).
  renameSession(sessionId: string, title: string): Promise<void> {
    this.renames.push({ sessionId, title });
    if (this.renameFails) {
      return Promise.reject(new Error("rename failed"));
    }
    this.sessions = this.sessions.map((s) => (s.sessionId === sessionId ? { ...s, title } : s));
    return Promise.resolve();
  }

  listDueReminders(): Promise<readonly DueReminder[]> {
    this.reminderListCalls += 1;
    if (this.remindersFail) {
      return Promise.reject(new Error("reminders failed"));
    }
    return Promise.resolve(this.reminders);
  }

  // Answers membership rather than a fixed `true`, so the fake reports "there was nothing to
  // clear" exactly where the brain would (an unknown or already-dismissed id). The table is not
  // mutated: what is still deliverable is the test's to say, as it is the brain's in production.
  ackReminder(reminderId: string): Promise<boolean> {
    this.acks.push(reminderId);
    if (this.ackFails) {
      return Promise.reject(new Error("ack failed"));
    }
    return Promise.resolve(this.reminders.some((r) => r.reminderId === reminderId));
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
