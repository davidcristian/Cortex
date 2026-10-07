# A stopped reply goes on writing, and is not kept

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md) decision 2
**Trigger:** a History line in this file recording the maintainer's pick of what a Stop keeps on
screen.
**Verified:** 2026-10-07

On the Linux shell a Stop pressed while the cortex wrote a long essay ended the turn in the brain at
once, and the overlay went on drawing the reply's text for at least 14 s
([readings](../../readings/overlay-turn-flows.md#with-the-abort)). The frame 0.4 s after the press
ended mid-word in the essay's first section, the frame 14 s after it ended a section further on
with the mist still on its last word, and the reply had settled by a frame 88 s after it.

The overlay draws a reply at the pace of the whisper front (`whisper/front.ts`), whose velocity is
clamped to `MAX_PACE`, 150 letters a second. On that run the cortex decoded faster than the front
drew, so by the Stop the overlay held text it had not drawn yet. The `stop` action in
`overlay/overlayState.ts` ends the reply with all the text received, and the bubble then draws the
rest at the same pace. A person who pressed Stop sees the reply keep coming.

The chat keeps none of it. The brain stores no reply for a cancelled turn
([ADR-0011](../../adr/ADR-0011-body-v1.md) decision 1), so a reopened chat shows the question
alone where the overlay showed part of a reply, and later prompts hold the question without it.

## Proposal

- **On screen** (recommended): a Stop cuts the reply to the letters the front had drawn at the
  press and settles there, so nothing appears after it. The alternative draws everything received
  at once on the press.
- **In the chat**: keep the question alone (today), or store what the overlay kept as a stopped
  reply. Storing it needs the drawn text to reach the brain, which no `ClientEvent` sends today.

## History

- 2026-10-07: filed from the Stop flow on the Linux shell after the shell's Stop started ending the
  turn in the brain.
