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

// Browser-dev BrainBridge: streams a canned reply on a timer so `vite dev` shows the real
// components with realistic streaming. Every string it serves lives in `demoScript.ts` and only
// the behaviour is here. Gated like any other implementation of the port: the shared checks in
// `bridgeContract.ts` drive it beside the fake, and `demoBridge.test.ts` covers what is only its
// own, the recorded conversation and the four prompts that trip a hook.
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

  // A chat the user has spoken in joins the list, which is what the brain does: the turn is
  // persisted and the next listing carries it, titled from the first message. Before this the
  // demo's list could only shrink, so a chat arriving was the one switcher case that could not be
  // driven by hand, and that is the case the empty line's mount rule turns on. The title comes from
  // `deriveTitle`, the brain's own rule applied locally, so the row that lands reads the same as
  // the header above it.
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
      pinned: false,
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
    // Say "screen" and the demo brain reports the capture built-in, so the header's capture ring
    // (ADR-0029) can be driven by hand like the outage and confirm-timeout hooks above it. Without
    // this the ring is unreachable in browser dev: it is lit by a `toolActivity` naming
    // `capture_screen`, and no other demo turn emits a tool activity at all.
    //
    // Both of its states are reachable here. The activity raises the ring to "asked", and the
    // outcome settling that dispatch is what advances it (ADR-0029 outcome addendum). Say "refused"
    // and the outcome comes back not ok, so the ring stays at the ask, which is what the shipping
    // default does with the host's capture switch unset. The 310ms between the two timers is long
    // enough to watch the change.
    //
    // The activity is dispatched from a timer rather than inside the call, short though its wait
    // is, because the shared check list asks whether a turn can deliver before it has handed back
    // its cancellation. The real bridge carries events over a Tauri channel and cannot, and a
    // caller assigns the handle from what `converse` returns.
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
    // Hold the bubble on the thinking animation, send a reasoning burst as thinking statuses, then
    // stream the reply, which is the order a real reasoning turn arrives in (ADR-0020). Several
    // deltas, so the accumulated trace has content both in the live chip and in the collapsed
    // "Thoughts" disclosure the deltas fold into once the reply settles (ADR-0020 addendum).
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
          // The demo brain answers for the user here, so the continuation is dropped first and a
          // click landing after the card closes resumes nothing (the stale-answer case,
          // fail-closed).
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
    // `0` means the brain's own default (`types.ts`) rather than a limit of none. Read as a limit,
    // it would answer an empty switcher to every caller that asks for the default listing.
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

  // A delete sticks, like the rename and the pin beside it. It was the last write left as a no-op
  // over the held list, which made the switcher's row exit impossible to watch by hand: the reducer
  // dropped the row, the refresh behind it listed the chat again, and the row that had just started
  // rolling out came straight back, taking the interrupted-exit path every time.
  deleteSession(sessionId: string): Promise<void> {
    this.sessions = this.sessions.filter((s) => s.sessionId !== sessionId);
    return Promise.resolve();
  }

  setSessionPinned(sessionId: string, pinned: boolean): Promise<void> {
    this.patch(sessionId, { pinned });
    return Promise.resolve();
  }
}
