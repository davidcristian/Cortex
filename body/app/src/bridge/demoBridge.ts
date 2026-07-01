import type { BrainBridge, Cancellation, TurnSink } from "./types";

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
}
