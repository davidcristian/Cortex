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

// Browser-dev BrainBridge: streams a canned reply on a timer so `vite dev` shows the real
// components with realistic streaming. Coverage-excluded as the frontend analog of the real Tauri
// bridge, exercised by hand (browser validation), never in CI.
export class DemoBridge implements BrainBridge {
  converse(_sessionId: string, _text: string, sink: TurnSink): Cancellation {
    const words = ANSWER.split(" ");
    let index = 0;
    const timer = setInterval(() => {
      const word = words[index];
      if (word === undefined) {
        clearInterval(timer);
        sink.onEvent({ kind: "complete", turnId: "demo" });
        return;
      }
      sink.onEvent({ kind: "delta", text: index === 0 ? word : ` ${word}` });
      index += 1;
    }, 55);
    return () => clearInterval(timer);
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
