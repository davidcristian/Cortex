# A streamed Hebrew reply is laid out left to right

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Verified:** 2026-10-15

Every settled bubble, the draft and the title take their direction from their first letter since
2026-10-15, but the whispering bubble does not
([readings](../../readings/overlay-long-and-unusual-input.md#right-to-left-text-combining-marks-and-emoji-sequences)).
A Hebrew or Arabic reply that streams in this shell therefore sits against the left edge with its
final period on the right, and keeps that layout until the chat is opened again, when it is drawn
as a settled bubble.

Setting the direction on the whispering bubble was tried on the Linux shell. With `dir="auto"` on
the bubble and `unicode-bidi: plaintext` on its `.wtxt` letters, a Hebrew reply drew as an empty
pill until its turn ended. With `dir="auto"` alone, the letters spilled past the bubble's left
edge while the box grew, and the mist glided in the wrong place. `useWhisperClock` measures and
poses the box, the front and the mist from the left edge.

## What to do

Make the clock's geometry follow the bubble's direction: measure letter positions from the
inline start edge, grow the posed box from it, and place the mist at the front's inline end. Test
it in `useWhisperClock.test.ts` with a right-to-left fixture, then set `dir="auto"` on the live
bubble and check a Hebrew and an Arabic reply frame by frame on the shell.

## History

- 2026-10-15: filed when the settled bubbles took their direction from their first letter.
