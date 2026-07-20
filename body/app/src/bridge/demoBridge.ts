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

const ANSWER =
  "The cortex stays resident on the GPU under the soft cap, and spawns small subagents when it " +
  "needs help. GPU-first when there's headroom, CPU otherwise. Nothing is lost on a model swap, " +
  "because every turn's state lives in the store, not the model.";

// A short reasoning trace streamed as thinking statuses before the reply, so the live chip and the
// settled collapsed "Thoughts" disclosure both have real content to show in browser dev (ADR-0020).
const REASONING =
  "The question is about where conversation state lives across a model swap. The invariant is that " +
  "no state sits in a model process, so the answer must ground itself in the external store rather " +
  "than the KV cache. Let me phrase that plainly.";

// The scripted confirm round (ADR-0022): a prompt that looks like a send walks the gated-tool
// path. First a short preamble, then a confirmRequest whose draft/reason mirror the brain's, then
// the reply continues (approve) or ends with a "not sent" line (deny).
const CONFIRM_PREAMBLE = "Here's the draft. Sending is gated, so it needs your approval first.";
const CONFIRM_REASON = "this action is outbound or irreversible and runs only with your approval";
// The attachment is here so the long-draft case is drivable by hand: it is the one argument
// meant to be long, and the card shows every value verbatim (ADR-0022 attachments addendum),
// so this is what proves `.confirm-draft` scrolls instead of pushing the buttons out of view.
const CONFIRM_DRAFT = JSON.stringify({
  to: "ada@example.com",
  subject: "Quick hello from Cortex",
  body: "Testing the send flow. Feel free to ignore this.",
  attachments: [
    {
      filename: "notes.md",
      subtype: "markdown",
      content: Array.from(
        { length: 24 },
        (_unused, line) => `- line ${line + 1} of the attached notes`,
      ).join("\n"),
    },
  ],
});
const CONFIRM_SENT = "Sent. Ada should have it in a moment. Anything else?";
const CONFIRM_DENIED = "Okay. Not sent, and the draft is discarded.";
// Say "timeout" in the prompt and the demo brain stops waiting after DEMO_CONFIRM_TIMEOUT_MS,
// as the real one does at CORTEX_SEAM_CONFIRM_TIMEOUT_S: it emits `confirmResolved`, the card
// closes on its own, and the declined reply resumes behind it (ADR-0022 resolution addendum).
// Four seconds rather than two minutes, so the behaviour is drivable by hand.
const DEMO_CONFIRM_TIMEOUT_MS = 4000;
const CONFIRM_TIMED_OUT = "You did not answer in time, so nothing was sent. Ask again any time.";

// The connection indicator is hand-drivable too (ADR-0011 addendum): say "offline" or
// "degraded" in a prompt and the demo brain reports that for a while, so amber, red, the
// pulse while a probe is out, and the recovery re-check are all visible in plain browser dev.
const DEMO_OUTAGE_MS = 12000;
const DEMO_READY_DETAIL = "cortex-orchestrator demo";
const DEMO_DOWN_DETAIL = "tcp connect error: connection refused";
const DEMO_DEGRADED_DETAIL = "Unavailable: the session store is down";

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
// components with realistic streaming. Coverage-excluded as the frontend analog of the real Tauri
// bridge, exercised by hand (browser validation), never in CI.
export class DemoBridge implements BrainBridge {
  /** Resumes the paused confirm turn with the user's decision (null = none pending). */
  private pending: ((approved: boolean) => void) | null = null;
  /** The demo brain's own deadline for that question, when the prompt asked for one. */
  private expiry: ReturnType<typeof setTimeout> | null = null;
  /** What the next probe reports, and when the scripted outage heals (0 = never went down). */
  private link: LinkState = "ready";
  private healsAt = 0;

  converse(_sessionId: string, text: string, sink: TurnSink): Cancellation {
    if (/offline|unreachable/iu.test(text)) {
      this.fail("down");
    } else if (/degraded|not ready/iu.test(text)) {
      this.fail("degraded");
    }
    if (/send|email/iu.test(text)) {
      return this.confirmTurn(sink, /time\s?out/iu.test(text));
    }
    // Say "screen" and the demo brain reports the capture built-in, so the header's capture ring
    // (ADR-0029) is drivable by hand like the outage and confirm-timeout hooks above it. Without
    // this the ring is unreachable in browser dev: it is lit by a `toolActivity` naming
    // `capture_screen`, and no other demo turn emits a tool activity at all, so the one indicator
    // whose whole job is to be seen was the one thing that could never be looked at.
    if (/screen|look at|see this/iu.test(text)) {
      sink.onEvent({
        kind: "toolActivity",
        toolName: "capture_screen",
        summary: "reading the screen",
      });
    }
    // Hold the bubble on the thinking shimmer, surface a reasoning burst as thinking statuses,
    // then stream: the same shape a real reasoning turn has (ADR-0020). Several deltas so the
    // accumulated trace is real, both as the live bobbing chip and, once the reply settles, as the
    // collapsed "Thoughts" disclosure the deltas fold into (ADR-0020 addendum).
    let cancelStream: Cancellation = () => undefined;
    const status = setTimeout(() => {
      cancelStream = streamWords(
        sink,
        REASONING,
        "",
        () => {
          cancelStream = streamWords(sink, ANSWER, "", () =>
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
    let cancel = streamWords(sink, CONFIRM_PREAMBLE, "", () => {
      const resume = (reply: string) => {
        cancel = streamWords(sink, reply, " ", () =>
          sink.onEvent({ kind: "complete", turnId: "demo" }),
        );
      };
      // Park the continuation before asking, because respondConfirm may answer immediately.
      this.pending = (approved) => resume(approved ? CONFIRM_SENT : CONFIRM_DENIED);
      sink.onEvent({
        kind: "confirmRequest",
        confirmId: "demo-confirm",
        toolName: "send_email",
        argumentsJson: CONFIRM_DRAFT,
        reason: CONFIRM_REASON,
      });
      if (expires) {
        this.expiry = setTimeout(() => {
          // The brain answered for the user: drop the continuation first, so a click landing
          // after the card closes resumes nothing (the stale-answer case, fail-closed).
          this.pending = null;
          sink.onEvent({ kind: "confirmResolved", confirmId: "demo-confirm", outcome: "timeout" });
          resume(CONFIRM_TIMED_OUT);
        }, DEMO_CONFIRM_TIMEOUT_MS);
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
    this.healsAt = Date.now() + DEMO_OUTAGE_MS;
  }

  checkLink(): Promise<LinkStatus> {
    if (this.healsAt !== 0 && Date.now() >= this.healsAt) {
      this.link = "ready";
      this.healsAt = 0;
    }
    const detail =
      this.link === "ready"
        ? DEMO_READY_DETAIL
        : this.link === "degraded"
          ? DEMO_DEGRADED_DETAIL
          : DEMO_DOWN_DETAIL;
    // A real probe rides the retrying transport, so a down brain answers slowly. Delay the
    // unhappy answers a little so the "checking" pulse is actually visible by hand.
    const delay = this.link === "ready" ? 120 : 900;
    return new Promise((resolve) =>
      setTimeout(() => resolve({ state: this.link, detail }), delay),
    );
  }

  listSessions(_limit: number): Promise<readonly SessionSummary[]> {
    return Promise.resolve([
      {
        // Pinned, and the OLDER of the two by activity, so it demonstrates pinning by hand: it
        // sorts ABOVE the newer chat in the switcher and carries the pin indicator, exactly the
        // read-path union the brain applies (ADR-0021 pinning addendum).
        sessionId: "demo-2",
        title: "Summarize my unread email",
        preview: "You have three unread threads…",
        lastActivityUnixMs: Date.now() - 3 * 60 * 60 * 1000,
        pinned: true,
      },
      {
        // A title deliberately unlike this chat's first message ("How does the model swap
        // work?"), standing in for a rename or a brain-generated title: opening the chat shows
        // this switcher title in the header, not the first message re-derived (ADR-0021
        // header-title addendum), so the consistency is visible by hand in browser dev.
        sessionId: "demo-1",
        title: "Everything about model swaps",
        preview: "The cortex is evicted and the brain loads…",
        lastActivityUnixMs: Date.now() - 5 * 60 * 1000,
        pinned: false,
      },
    ]);
  }

  // Reminder pull delivery (ADR-0025). Three cards covering the shapes that render
  // differently: a plain one, a recurring one, and one carrying untrusted provenance.
  // Dismissing acks against the local table, so the stack empties as it would for real.
  private due: readonly DueReminder[] = [
    {
      reminderId: "demo-r1",
      text: "Stretch. You have been at this for an hour.",
      firedAtUnixMs: Date.now() - 4 * 60 * 1000,
      recurring: false,
      tainted: false,
      sessionId: "demo-1",
    },
    {
      reminderId: "demo-r2",
      text: "Stand-up in 10 minutes.",
      firedAtUnixMs: Date.now() - 90 * 1000,
      recurring: true,
      tainted: false,
      sessionId: "demo-2",
    },
    {
      reminderId: "demo-r3",
      text: "Confirm the invoice from the email thread before Friday.",
      firedAtUnixMs: Date.now() - 40 * 60 * 1000,
      recurring: false,
      tainted: true,
      sessionId: "demo-2",
    },
  ];

  // The user's settings record (ADR-0032). Held in memory for browser dev, so picking a mark or
  // a theme sticks across a re-summon within the session the way the real record sticks across a
  // restart; a reload starts fresh, since there is no brain here to hold it.
  private prefs: Preference[] = [];

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
    if (sessionId === "demo-2") {
      return Promise.resolve([
        { role: "user", text: "Summarize my unread email", turnId: "t2", atUnixMs: 0 },
        {
          role: "assistant",
          text: "You have three unread threads: a deploy failure from CI, a review request on the seam PR, and a calendar invite for Thursday.",
          turnId: "t2",
          atUnixMs: 0,
        },
      ]);
    }
    return Promise.resolve([
      { role: "user", text: "How does the model swap work?", turnId: "t1", atUnixMs: 0 },
      { role: "assistant", text: ANSWER, turnId: "t1", atUnixMs: 0 },
    ]);
  }

  // The demo list is static, so a rename is a no-op that resolves; the browser-dev switcher
  // just does not persist the relabel (the real bridge does, over the seam).
  renameSession(_sessionId: string, _title: string): Promise<void> {
    return Promise.resolve();
  }

  // Likewise a delete is a no-op that resolves: the demo list is static, so the browser-dev
  // switcher shows the row leave optimistically but does not persist it (the real bridge does).
  deleteSession(_sessionId: string): Promise<void> {
    return Promise.resolve();
  }

  // A pin toggle is a no-op that resolves too: the demo list is static, so the browser-dev
  // switcher re-lists to its canned pinned-first order (the real bridge persists over the seam).
  setSessionPinned(_sessionId: string, _pinned: boolean): Promise<void> {
    return Promise.resolve();
  }
}
