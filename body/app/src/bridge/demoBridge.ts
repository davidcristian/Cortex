import * as script from "./demoScript";
import type {
  BrainBridge,
  Cancellation,
  DueReminder,
  LinkState,
  LinkStatus,
  Preference,
  SessionMessage,
  SessionSummary,
  TurnSink,
} from "./types";

/** Stream `text` word by word; `lead` prefixes the first word. By default each word is a reply
 *  `delta`; pass `emit` to route the words elsewhere (the reasoning burst sends them as thinking
 *  statuses instead), keeping the same paced-word shape for both surfaces. */
function streamWords(
  sink: TurnSink,
  text: string,
  lead: string,
  onDone: () => void,
  emit: (delta: string) => void = (delta) => sink.onEvent({ kind: "delta", text: delta }),
): Cancellation {
  const words = text.split(" ");
  let index = 0;
  const timer = setInterval(() => {
    const word = words[index];
    if (word === undefined) {
      clearInterval(timer);
      onDone();
      return;
    }
    emit(index === 0 ? lead + word : ` ${word}`);
    index += 1;
  }, 55);
  return () => clearInterval(timer);
}

export class DemoBridge implements BrainBridge {
  /** Resumes the paused confirm turn with the user's decision (null = none pending). */
  private pending: ((approved: boolean) => void) | null = null;
  /** The demo brain's own deadline for that question, when the prompt asked for one. */
  private expiry: ReturnType<typeof setTimeout> | null = null;
  /** What the next probe reports, and when the scripted outage heals (0 = never went down). */
  private link: LinkState = "ready";
  private healsAt = 0;
  // Held rather than rebuilt per call, so the writes below actually stick for the session. They
  // used to be no-ops over a static list, which made rename, delete and pin unexercisable by hand:
  // the row changed optimistically and the next re-list put it straight back.
  private sessions: SessionSummary[] = script.sessions();
  private due: readonly DueReminder[] = script.reminders();
  // The user's settings record (ADR-0032). Held in memory for browser dev, so picking a mark or
  // a theme sticks across a re-summon within the session the way the real record sticks across a
  // restart; a reload starts fresh, since there is no brain here to hold it.
  private prefs: Preference[] = [];

  converse(_sessionId: string, text: string, sink: TurnSink): Cancellation {
    if (/offline|unreachable/iu.test(text)) {
      this.fail("down");
    } else if (/degraded|not ready/iu.test(text)) {
      this.fail("degraded");
    }
    if (/send|email/iu.test(text)) {
      return this.confirmTurn(sink, /time\s?out/iu.test(text));
    }
    if (/screen|look at|see this/iu.test(text)) {
      sink.onEvent({
        kind: "toolActivity",
        toolName: "capture_screen",
        summary: "reading the screen",
      });
    }
    let cancelStream: Cancellation = () => undefined;
    const status = setTimeout(() => {
      cancelStream = streamWords(
        sink,
        script.REASONING,
        "",
        () => {
          cancelStream = streamWords(sink, script.ANSWER, "", () =>
            sink.onEvent({ kind: "complete", turnId: "demo" }),
          );
        },
        (delta) => sink.onEvent({ kind: "status", state: "thinking", detail: delta }),
      );
    }, 450);
    return () => {
      clearTimeout(status);
      cancelStream();
    };
  }

  private confirmTurn(sink: TurnSink, expires: boolean): Cancellation {
    let cancel = streamWords(sink, script.CONFIRM_PREAMBLE, "", () => {
      const resume = (reply: string) => {
        cancel = streamWords(sink, reply, " ", () =>
          sink.onEvent({ kind: "complete", turnId: "demo" }),
        );
      };
      // Park the continuation before asking, because respondConfirm may answer immediately.
      this.pending = (approved) => resume(approved ? script.CONFIRM_SENT : script.CONFIRM_DENIED);
      sink.onEvent({
        kind: "confirmRequest",
        confirmId: "demo-confirm",
        toolName: "send_email",
        argumentsJson: script.CONFIRM_DRAFT,
        reason: script.CONFIRM_REASON,
      });
      if (expires) {
        this.expiry = setTimeout(() => {
          // The brain answered for the user: drop the continuation first, so a click landing
          // after the card closes resumes nothing (the stale-answer case, fail-closed).
          this.pending = null;
          sink.onEvent({ kind: "confirmResolved", confirmId: "demo-confirm", outcome: "timeout" });
          resume(script.CONFIRM_TIMED_OUT);
        }, script.CONFIRM_TIMEOUT_MS);
      }
    });
    return () => {
      this.clearPending();
      cancel();
    };
  }

  respondConfirm(_confirmId: string, approved: boolean): Promise<void> {
    const resume = this.pending;
    this.clearPending();
    resume?.(approved);
    return Promise.resolve();
  }

  /** Forget the open question and its deadline, so neither path can resume the turn twice. */
  private clearPending(): void {
    this.pending = null;
    if (this.expiry !== null) {
      clearTimeout(this.expiry);
      this.expiry = null;
    }
  }

  /** Script an outage that heals on its own, so the recovery re-check has something to find. */
  private fail(state: LinkState): void {
    this.link = state;
    this.healsAt = Date.now() + script.OUTAGE_MS;
  }

  checkLink(): Promise<LinkStatus> {
    if (this.healsAt !== 0 && Date.now() >= this.healsAt) {
      this.link = "ready";
      this.healsAt = 0;
    }
    const detail =
      this.link === "ready"
        ? script.READY_DETAIL
        : this.link === "degraded"
          ? script.DEGRADED_DETAIL
          : script.DOWN_DETAIL;
    // A real probe rides the retrying transport, so a down brain answers slowly. Delay the
    // unhappy answers a little so the "checking" pulse is actually visible by hand.
    const delay = this.link === "ready" ? 120 : 900;
    return new Promise((resolve) =>
      setTimeout(() => resolve({ state: this.link, detail }), delay),
    );
  }

  listSessions(limit: number): Promise<readonly SessionSummary[]> {
    // Pinned first, then by recency, which is the order the brain lists in (ADR-0021).
    const ordered = [...this.sessions].sort(
      (a, b) =>
        Number(b.pinned) - Number(a.pinned) || b.lastActivityUnixMs - a.lastActivityUnixMs,
    );
    return Promise.resolve(ordered.slice(0, limit));
  }

  getPreferences(): Promise<readonly Preference[]> {
    return Promise.resolve([...this.prefs]);
  }

  setPreference(key: string, value: string): Promise<void> {
    this.prefs = this.prefs.filter((pref) => pref.key !== key);
    if (value !== "") {
      this.prefs.push({ key, value });
    }
    return Promise.resolve();
  }

  listDueReminders(): Promise<readonly DueReminder[]> {
    return Promise.resolve(this.due);
  }

  ackReminder(reminderId: string): Promise<boolean> {
    const before = this.due.length;
    this.due = this.due.filter((reminder) => reminder.reminderId !== reminderId);
    return Promise.resolve(this.due.length < before);
  }

  sessionMessages(sessionId: string): Promise<readonly SessionMessage[]> {
    return Promise.resolve(script.transcript(sessionId));
  }

  private patch(sessionId: string, change: Partial<SessionSummary>): void {
    this.sessions = this.sessions.map((s) => (s.sessionId === sessionId ? { ...s, ...change } : s));
  }

  /** An empty title clears the override, which the real store expresses the same way. */
  renameSession(sessionId: string, title: string): Promise<void> {
    this.patch(sessionId, { title: title === "" ? "New chat" : title });
    return Promise.resolve();
  }

  // Likewise a delete is a no-op that resolves: the demo list is static, so the browser-dev
  // switcher shows the row leave optimistically but does not persist it (the real bridge does).
  deleteSession(_sessionId: string): Promise<void> {
    return Promise.resolve();
  }

  setSessionPinned(sessionId: string, pinned: boolean): Promise<void> {
    this.patch(sessionId, { pinned });
    return Promise.resolve();
  }
}
