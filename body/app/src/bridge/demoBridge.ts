import type {
  BrainBridge,
  Cancellation,
  SessionMessage,
  SessionSummary,
  TurnSink,
} from "./types";

const ANSWER =
  "The cortex stays resident on the GPU under the soft cap, and spawns small subagents when it " +
  "needs help. GPU-first when there's headroom, CPU otherwise. Nothing is lost on a model swap, " +
  "because every turn's state lives in the store, not the model.";

// The scripted confirm round (ADR-0022): a prompt that looks like a send walks the gated-tool
// path. First a short preamble, then a confirmRequest whose draft/reason mirror the brain's, then
// the reply continues (approve) or ends with a "not sent" line (deny).
const CONFIRM_PREAMBLE = "Here's the draft. Sending is gated, so it needs your approval first.";
const CONFIRM_REASON = "this action is outbound or irreversible and runs only with your approval";
const CONFIRM_DRAFT = JSON.stringify({
  to: "ada@example.com",
  subject: "Quick hello from Cortex",
  body: "Testing the send flow. Feel free to ignore this.",
});
const CONFIRM_SENT = "Sent. Ada should have it in a moment. Anything else?";
const CONFIRM_DENIED = "Okay. Not sent, and the draft is discarded.";

/** Stream `text` word by word into an in-progress reply; `lead` prefixes the first word. */
function streamWords(sink: TurnSink, text: string, lead: string, onDone: () => void): Cancellation {
  const words = text.split(" ");
  let index = 0;
  const timer = setInterval(() => {
    const word = words[index];
    if (word === undefined) {
      clearInterval(timer);
      onDone();
      return;
    }
    sink.onEvent({ kind: "delta", text: index === 0 ? lead + word : ` ${word}` });
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

  converse(_sessionId: string, text: string, sink: TurnSink): Cancellation {
    if (/send|email/iu.test(text)) {
      return this.confirmTurn(sink);
    }
    // Hold the bubble on the thinking shimmer, surface a status chip, then stream: the same
    // shape a real reasoning turn has (ADR-0020), so the working affordances are visible here.
    let cancelStream: Cancellation = () => undefined;
    const status = setTimeout(() => {
      sink.onEvent({ kind: "status", state: "thinking", detail: "planning the answer" });
    }, 450);
    const start = setTimeout(() => {
      cancelStream = streamWords(sink, ANSWER, "", () =>
        sink.onEvent({ kind: "complete", turnId: "demo" }),
      );
    }, 1100);
    return () => {
      clearTimeout(status);
      clearTimeout(start);
      cancelStream();
    };
  }

  private confirmTurn(sink: TurnSink): Cancellation {
    let cancel = streamWords(sink, CONFIRM_PREAMBLE, "", () => {
      // Park the continuation before asking, because respondConfirm may answer immediately.
      this.pending = (approved) => {
        cancel = streamWords(sink, approved ? CONFIRM_SENT : CONFIRM_DENIED, " ", () =>
          sink.onEvent({ kind: "complete", turnId: "demo" }),
        );
      };
      sink.onEvent({
        kind: "confirmRequest",
        confirmId: "demo-confirm",
        toolName: "send_email",
        argumentsJson: CONFIRM_DRAFT,
        reason: CONFIRM_REASON,
      });
    });
    return () => {
      this.pending = null;
      cancel();
    };
  }

  respondConfirm(_confirmId: string, approved: boolean): Promise<void> {
    this.pending?.(approved);
    this.pending = null;
    return Promise.resolve();
  }

  listSessions(_limit: number): Promise<readonly SessionSummary[]> {
    return Promise.resolve([
      {
        sessionId: "demo-1",
        title: "How does the model swap work?",
        preview: "The cortex is evicted and the brain loads…",
        lastActivityUnixMs: Date.now() - 5 * 60 * 1000,
      },
      {
        sessionId: "demo-2",
        title: "Summarize my unread email",
        preview: "You have three unread threads…",
        lastActivityUnixMs: Date.now() - 3 * 60 * 60 * 1000,
      },
    ]);
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
}
