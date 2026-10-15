# A long Hebrew or emoji reply segments its whole text on every render

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Verified:** 2026-10-15

The whispering bubble re-renders on every streamed delta, and each render splits the whole reply
into letters four times: `tokenize`, `letterCountOf` (called again inside `confirmedOf`) and the
render's `lettersOf` per word (`body/app/src/whisper/front.ts`, `components/WhisperBubble.tsx`).
Since letters are graphemes, those passes go through `Intl.Segmenter`. Timed in headless
Chromium, the engine WebView2 uses, the four passes over a 20,000-character reply took 77 times as
long with the segmenter as by code point in English and 60 times as long in Hebrew, and over 2,000
characters 32 and 52 times as long. A text with no code point at or above U+0300 is now split by
code point, which brought English back to 3 times the old cost; a Hebrew, Arabic or emoji reply
still pays the segmenter on every render
([readings](../../readings/overlay-long-and-unusual-input.md#right-to-left-text-combining-marks-and-emoji-sequences)).
The reply has no token bound unless `CORTEX_REPLY_MAX_TOKENS` sets one, so a long reply is bounded
only by the context.

## What to do

Segment each word once per render: let `tokenize` keep each word token's letters on the token, so
`letterCountOf`, `confirmedOf` and the render read them instead of splitting again. Then keep the
tokens of the confirmed part across renders, so a render segments only the growing last word.
Time the same four passes again over a 20,000-character Hebrew reply and check they cost no more
than a few times the code point split, and that no left to right frame changes.

## History

- 2026-10-15: filed by the closing audit, which measured the cost and split text below U+0300 by
  code point.
