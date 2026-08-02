// The browser-dev demo's canned script: everything `demoBridge.ts` says or serves, with no
// behaviour of its own. Split out on 2026-08-03 when the line cap started measuring the overlay
// (ADR-0011 line-cap addendum) and the bridge stood at 351 lines. Coverage-excluded beside the
// bridge in `vite.config.ts`, for the same reason the bridge is: nothing imports either but the
// entry glue, and the demo is exercised by hand in a browser rather than in CI.
import type { DueReminder, SessionMessage, SessionSummary } from "./types";

export const ANSWER =
  "The cortex stays resident on the GPU under the soft cap, and spawns small subagents when it " +
  "needs help. GPU-first when there's headroom, CPU otherwise. Nothing is lost on a model swap, " +
  "because every turn's state lives in the store, not the model.";

// A short reasoning trace streamed as thinking statuses before the reply, so the live chip and the
// settled collapsed "Thoughts" disclosure both have real content to show in browser dev (ADR-0020).
export const REASONING =
  "The question is about where conversation state lives across a model swap. The invariant is that " +
  "no state sits in a model process, so the answer must ground itself in the external store rather " +
  "than the KV cache. Let me phrase that plainly.";

// The scripted confirm round (ADR-0022): a prompt that looks like a send walks the gated-tool
// path. First a short preamble, then a confirmRequest whose draft/reason mirror the brain's, then
// the reply continues (approve) or ends with a "not sent" line (deny).
export const CONFIRM_PREAMBLE = "Here's the draft. Sending is gated, so it needs your approval first.";
export const CONFIRM_REASON =
  "this action is outbound or irreversible and runs only with your approval";
// The attachment is here so the long-draft case is drivable by hand: it is the one argument
// meant to be long, and the card shows every value verbatim (ADR-0022 attachments addendum),
// so this is what proves `.confirm-draft` scrolls instead of pushing the buttons out of view.
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
// Say "timeout" in the prompt and the demo brain stops waiting after CONFIRM_TIMEOUT_MS,
// as the real one does at CORTEX_SEAM_CONFIRM_TIMEOUT_S: it emits `confirmResolved`, the card
// closes on its own, and the declined reply resumes behind it (ADR-0022 resolution addendum).
// Four seconds rather than two minutes, so the behaviour is drivable by hand.
export const CONFIRM_TIMEOUT_MS = 4000;
export const CONFIRM_TIMED_OUT = "You did not answer in time, so nothing was sent. Ask again any time.";

// The connection indicator is hand-drivable too (ADR-0011 addendum): say "offline" or
// "degraded" in a prompt and the demo brain reports that for a while, so amber, red, the
// pulse while a probe is out, and the recovery re-check are all visible in plain browser dev.
export const OUTAGE_MS = 12000;
export const READY_DETAIL = "cortex-orchestrator demo";
export const DOWN_DETAIL = "tcp connect error: connection refused";
export const DEGRADED_DETAIL = "Unavailable: the session store is down";

/** The switcher's seed. A function rather than a constant so each `DemoBridge` gets activity
 *  stamps relative to its own construction, exactly as the inline initializer did, and so the
 *  bridge can mutate its copy without writing back into the script. */
export function sessions(): SessionSummary[] {
  return [
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
  ];
}

/** Reminder pull delivery (ADR-0025). Three cards covering the shapes that render differently:
 *  a plain one, a recurring one, and one carrying untrusted provenance. Dismissing acks against
 *  the bridge's own copy, so the stack empties as it would for real. */
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

/** The stored history behind each seeded chat, so re-opening one in the switcher restores a
 *  conversation rather than an empty stage. Any id but `demo-2` gets the model-swap chat, which
 *  is also the one a cold start adopts. */
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
