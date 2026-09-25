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

// A hand-driven fake `BrainBridge` for tests: `converse` records the call and keeps the sink, so
// the test decides when events, completion and failures arrive. The session reads resolve from
// tables the test assigns, or reject when a failure flag is set.
export class FakeBridge implements BrainBridge {
  private sink: TurnSink | null = null;
  readonly calls: { readonly sessionId: string; readonly text: string }[] = [];
  /** The pictures each `converse` call sent, parallel to `calls`. */
  readonly attached: (readonly AttachedImage[])[] = [];
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
  /** Rename writes received, in order: session id and new title. */
  readonly renames: { readonly sessionId: string; readonly title: string }[] = [];
  /** Delete writes received, in order: session id. */
  readonly deletes: string[] = [];
  /** `setSessionHoisted` writes received, in order: session id and target state. */
  readonly hoists: { readonly sessionId: string; readonly hoisted: boolean }[] = [];
  /** When set, the matching read rejects (the transport-failure path). */
  listFails = false;
  messagesFail = false;
  /** When set, `renameSession` rejects (a lost write, so the list is left unrelabelled). */
  renameFails = false;
  /** When set, `deleteSession` rejects (a lost destructive write, so nothing is dropped). */
  deleteFails = false;
  /** When set, `setSessionHoisted` rejects (a lost write, so the list keeps its old grouping). */
  hoistFails = false;
  /** When set, `respondConfirm` rejects (a lost answer, so deny-by-timeout brain-side). */
  confirmFails = false;
  /** What `listDueReminders` resolves with (assignable by a test; ADR-0025). */
  reminders: readonly DueReminder[] = [];
  /** How many times the overlay pulled the due list (proves the open latch fires once). */
  reminderListCalls = 0;
  /** Reminder ids acked so far, in order. */
  readonly acks: { readonly reminderId: string; readonly firedAtUnixMs: number }[] = [];
  /** When set, the matching reminder call rejects (an unreachable brain). */
  remindersFail = false;
  ackFails = false;
  /** What `checkLink` resolves with (assignable by a test; ADR-0011 decision 8). */
  link: LinkStatus = { state: "ready", detail: "fake brain", notes: [] };
  /** How many probes the overlay has fired (proves the summon latch + recovery cadence). */
  linkCalls = 0;
  /** When set, `checkLink` rejects: the IPC failed, which says nothing about the brain. */
  linkFails = false;
  /** When set, `checkLink` never settles, so a test can hold a probe in flight. */
  linkHangs = false;

  converse(
    sessionId: string,
    text: string,
    images: readonly AttachedImage[],
    sink: TurnSink,
  ): Cancellation {
    this.calls.push({ sessionId, text });
    this.attached.push(images);
    this.sink = sink;
    return () => {
      this.sink = null;
    };
  }

  // The real command answers a state even for an unreachable brain, so the default resolves;
  // `linkFails` is the narrower case of the IPC itself failing.
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

  // Bounded by `limit` like the real read, so a test cannot pass against rows production would
  // cut. `0` means the brain's default, which for a table the test assigned is all of it.
  listSessions(limit: number): Promise<readonly SessionSummary[]> {
    this.listCalls += 1;
    if (this.listFails) {
      return Promise.reject(new Error("list failed"));
    }
    return Promise.resolve(limit === 0 ? this.sessions : this.sessions.slice(0, limit));
  }

  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]> {
    this.messagesCalls.push(sessionId);
    if (this.messagesFail) {
      return Promise.reject(new Error("history failed"));
    }
    return Promise.resolve(this.messagesBySession[sessionId] ?? []);
  }

  renameSession(sessionId: string, title: string): Promise<void> {
    this.renames.push({ sessionId, title });
    if (this.renameFails) {
      return Promise.reject(new Error("rename failed"));
    }
    this.sessions = this.sessions.map((s) => (s.sessionId === sessionId ? { ...s, title } : s));
    return Promise.resolve();
  }

  deleteSession(sessionId: string): Promise<void> {
    this.deletes.push(sessionId);
    if (this.deleteFails) {
      return Promise.reject(new Error("delete failed"));
    }
    this.sessions = this.sessions.filter((s) => s.sessionId !== sessionId);
    return Promise.resolve();
  }

  setSessionHoisted(sessionId: string, hoisted: boolean): Promise<void> {
    this.hoists.push({ sessionId, hoisted });
    if (this.hoistFails) {
      return Promise.reject(new Error("hoist failed"));
    }
    const updated = this.sessions.map((s) => (s.sessionId === sessionId ? { ...s, hoisted } : s));
    // A stable sort, so the order inside each group stays as it was.
    this.sessions = [...updated].sort((a, b) => Number(b.hoisted) - Number(a.hoisted));
    return Promise.resolve();
  }

  /** The stored settings the overlay hydrates from (assignable by a test; ADR-0032). */
  preferences: readonly Preference[] = [];
  /** How many times the overlay read the record (proves the hydrate latch fires once). */
  preferenceReads = 0;
  /** Every write the overlay made, in order, the clearing empty values included. */
  readonly preferenceWrites: { readonly key: string; readonly value: string }[] = [];
  /** When set, the matching preference call rejects (an unreachable or store-down brain). */
  preferencesFail = false;
  preferenceWriteFails = false;

  getPreferences(): Promise<readonly Preference[]> {
    this.preferenceReads += 1;
    if (this.preferencesFail) {
      return Promise.reject(new Error("preferences failed"));
    }
    return Promise.resolve(this.preferences);
  }

  setPreference(key: string, value: string): Promise<void> {
    this.preferenceWrites.push({ key, value });
    if (this.preferenceWriteFails) {
      return Promise.reject(new Error("preference write failed"));
    }
    const others = this.preferences.filter((pref) => pref.key !== key);
    this.preferences = value === "" ? others : [...others, { key, value }];
    return Promise.resolve();
  }

  listDueReminders(): Promise<readonly DueReminder[]> {
    this.reminderListCalls += 1;
    if (this.remindersFail) {
      return Promise.reject(new Error("reminders failed"));
    }
    return Promise.resolve(this.reminders);
  }

  // Answers whether the row is there rather than a fixed `true`, and leaves the table alone:
  // what is still deliverable is the test's to decide, as it is the brain's in production.
  ackReminder(reminderId: string, firedAtUnixMs: number): Promise<boolean> {
    this.acks.push({ reminderId, firedAtUnixMs });
    if (this.ackFails) {
      return Promise.reject(new Error("ack failed"));
    }
    return Promise.resolve(
      this.reminders.some((r) => r.reminderId === reminderId && r.firedAtUnixMs === firedAtUnixMs),
    );
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
