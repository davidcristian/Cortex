import { deriveTitle } from "../overlay/sessionState";
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

/** Stream `text` word by word; `lead` prefixes the first word. `emit` sends the words somewhere
 *  other than a reply `delta`, which the reasoning burst uses to send them as thinking statuses. */
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

// A `BrainBridge` for browser development: it streams a canned reply on a timer so `vite dev`
// shows the real components. Every string it serves lives in `demoScript.ts`.
export class DemoBridge implements BrainBridge {
  /** Resumes the paused confirm turn with the user's decision (null = none pending). */
  private pending: ((approved: boolean) => void) | null = null;
  /** The demo brain's own deadline for that question, when the prompt asked for one. */
  private expiry: ReturnType<typeof setTimeout> | null = null;
  /** What the next probe reports, and when the scripted outage ends (0 = never went down). */
  private link: LinkState = "ready";
  private recoversAt = 0;
  private sessions: SessionSummary[] = script.sessions();
  private due: readonly DueReminder[] = script.reminders();
  private prefs: Preference[] = [];

  private remember(sessionId: string, text: string): void {
    if (this.sessions.some((held) => held.sessionId === sessionId)) {
      this.patch(sessionId, { preview: text, lastActivityUnixMs: Date.now() });
      return;
    }
    this.sessions.push({
      sessionId,
      title: deriveTitle(text),
      preview: text,
      lastActivityUnixMs: Date.now(),
      hoisted: false,
    });
  }

  converse(sessionId: string, text: string, sink: TurnSink): Cancellation {
    this.remember(sessionId, text);
    if (/offline|unreachable/iu.test(text)) {
      this.fail("down");
    } else if (/degraded|not ready/iu.test(text)) {
      this.fail("degraded");
    }
    if (/send|email/iu.test(text)) {
      return this.confirmTurn(sink, /time\s?out/iu.test(text));
    }
    // Say "screen" in a prompt to drive the header's capture indicator, and add "refused" to make
    // the outcome come back not ok. Both timers fire after `converse` returns, because the shared
    // check list asks whether a turn delivers anything before it has been handed its cancellation.
    let asked: ReturnType<typeof setTimeout> | undefined;
    let settle: ReturnType<typeof setTimeout> | undefined;
    if (/screen|look at|see this/iu.test(text)) {
      const ok = !/refus|blocked|denied|declin/iu.test(text);
      asked = setTimeout(() => {
        sink.onEvent({
          kind: "toolActivity",
          toolName: "capture_screen",
          summary: "reading the screen",
        });
      }, 90);
      settle = setTimeout(() => {
        sink.onEvent({ kind: "toolOutcome", toolName: "capture_screen", ok });
      }, 400);
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
      clearTimeout(asked);
      clearTimeout(settle);
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
      // Store the continuation before asking, because `respondConfirm` may answer at once.
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
          // Drop the continuation first, so a click arriving after the card closes resumes nothing.
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

  /** Clear the open question and its deadline, so neither path can resume the turn twice. */
  private clearPending(): void {
    this.pending = null;
    if (this.expiry !== null) {
      clearTimeout(this.expiry);
      this.expiry = null;
    }
  }

  /** Script an outage that ends on its own, so the recovery re-check has something to find. */
  private fail(state: LinkState): void {
    this.link = state;
    this.recoversAt = Date.now() + script.OUTAGE_MS;
  }

  checkLink(): Promise<LinkStatus> {
    if (this.recoversAt !== 0 && Date.now() >= this.recoversAt) {
      this.link = "ready";
      this.recoversAt = 0;
    }
    const detail =
      this.link === "ready"
        ? script.READY_DETAIL
        : this.link === "degraded"
          ? script.DEGRADED_DETAIL
          : script.DOWN_DETAIL;
    // The unhappy answers are slower, so the "checking" pulse is long enough to watch by hand.
    const delay = this.link === "ready" ? 120 : 900;
    return new Promise((resolve) =>
      setTimeout(() => resolve({ state: this.link, detail, notes: [] }), delay),
    );
  }

  listSessions(limit: number): Promise<readonly SessionSummary[]> {
    const ordered = [...this.sessions].sort(
      (a, b) =>
        Number(b.hoisted) - Number(a.hoisted) || b.lastActivityUnixMs - a.lastActivityUnixMs,
    );
    // `0` means the brain's own default listing, not a limit of none.
    return Promise.resolve(limit === 0 ? ordered : ordered.slice(0, limit));
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

  ackReminder(reminderId: string, firedAtUnixMs: number): Promise<boolean> {
    const before = this.due.length;
    this.due = this.due.filter(
      (reminder) => reminder.reminderId !== reminderId || reminder.firedAtUnixMs !== firedAtUnixMs,
    );
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

  deleteSession(sessionId: string): Promise<void> {
    this.sessions = this.sessions.filter((s) => s.sessionId !== sessionId);
    return Promise.resolve();
  }

  setSessionHoisted(sessionId: string, hoisted: boolean): Promise<void> {
    this.patch(sessionId, { hoisted });
    return Promise.resolve();
  }
}
