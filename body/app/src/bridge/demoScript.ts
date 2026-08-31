// Every canned string and seed row the demo bridge serves. No behavior lives here.
import type { DueReminder, SessionMessage, SessionSummary } from "./types";

export const ANSWER =
  "The cortex stays resident on the GPU under the soft cap, and spawns small subagents when it " +
  "needs help. GPU-first when there's headroom, CPU otherwise. Nothing is lost on a model swap, " +
  "because every turn's state lives in the store, not the model.";

export const REASONING =
  "The question is about where conversation state lives across a model swap. The invariant is that " +
  "no state sits in a model process, so the answer must ground itself in the external store rather " +
  "than the KV cache. Let me phrase that plainly.";

export const CONFIRM_PREAMBLE = "Here's the draft. Sending is gated, so it needs your approval first.";
export const CONFIRM_REASON =
  "this action is outbound or irreversible and runs only with your approval";
export const CONFIRM_DRAFT = JSON.stringify({
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
export const CONFIRM_SENT = "Sent. Ada should have it in a moment. Anything else?";
export const CONFIRM_DENIED = "Okay. Not sent, and the draft is discarded.";
// Four seconds rather than the brain's two minutes, so the timeout can be watched by hand.
export const CONFIRM_TIMEOUT_MS = 4000;
export const CONFIRM_TIMED_OUT = "You did not answer in time, so nothing was sent. Ask again any time.";

// Say "offline" or "degraded" in a prompt and the demo reports that state for this long.
export const OUTAGE_MS = 12000;
export const READY_DETAIL = "cortex-orchestrator demo";
export const DOWN_DETAIL = "tcp connect error: connection refused";
export const DEGRADED_DETAIL = "Unavailable: the session store is down";

/** The switcher's seed rows. A function rather than a constant, so each `DemoBridge` gets
 *  activity times relative to its own construction and can change its own copy. */
export function sessions(): SessionSummary[] {
  return [
    {
      sessionId: "demo-2",
      title: "Summarize my unread email",
      preview: "You have three unread threads…",
      lastActivityUnixMs: Date.now() - 3 * 60 * 60 * 1000,
      pinned: true,
    },
    {
      // The title is deliberately unlike this chat's first message, so opening the chat shows
      // the stored title in the header rather than one derived from the message again.
      sessionId: "demo-1",
      title: "Everything about model swaps",
      preview: "The cortex is evicted and the brain loads…",
      lastActivityUnixMs: Date.now() - 5 * 60 * 1000,
      pinned: false,
    },
    {
      sessionId: "demo-3",
      title: "Reminders and recurrence",
      preview: "Every weekday at nine, in your timezone…",
      lastActivityUnixMs: Date.now() - 40 * 60 * 1000,
      pinned: false,
    },
  ];
}

/** Three reminder cards, covering the forms that render differently: a plain one, a repeating
 *  one, and one whose text came from an untrusted source. */
export function reminders(): readonly DueReminder[] {
  return [
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
}

/** The stored history behind each seeded chat, so re-opening one restores a conversation rather
 *  than an empty log. Any id but `demo-2` gets the model-swap chat. */
export function transcript(sessionId: string): readonly SessionMessage[] {
  if (sessionId === "demo-2") {
    return [
      { role: "user", text: "Summarize my unread email", turnId: "t2", atUnixMs: 0 },
      {
        role: "assistant",
        text: "You have three unread threads: a deploy failure from CI, a review request on the seam PR, and a calendar invite for Thursday.",
        turnId: "t2",
        atUnixMs: 0,
      },
    ];
  }
  return [
    { role: "user", text: "How does the model swap work?", turnId: "t1", atUnixMs: 0 },
    { role: "assistant", text: ANSWER, turnId: "t1", atUnixMs: 0 },
  ];
}
