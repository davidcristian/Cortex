# A phrase in the other direction streams with its words reversed

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Verified:** 2026-10-15

A streamed reply takes one direction from its first letter, and each of its words is an
inline-block box, which the bidirectional algorithm treats as a neutral character. A run of words
in the other direction is therefore laid out in the reply's direction, word by word. Streamed in
headless Chromium, "Cortex keeps every turn in the store: המצב נשמר במאגר החיצוני" showed the
Hebrew words left to right in the order they were written, so a Hebrew reader reads the phrase
backwards; an English phrase inside a Hebrew reply would read backwards the same way. The Linux
shell's WebKitGTK drew a two-word Hebrew phrase in an English reply in the right order, so the
defect is Chromium's, which is the engine of the Windows body's WebView2
([readings](../../readings/overlay-long-and-unusual-input.md#right-to-left-text-combining-marks-and-emoji-sequences)).
Each word's own letters are in the right order, and the reply is correct once the chat is opened
again, when it is drawn as a settled bubble.

## What to do

Make a word box take part in the bidirectional ordering of its line without becoming breakable
mid-glide, for example an inline span with `white-space: nowrap` instead of an inline-block, and
check that no left-to-right frame changes (letter advances stay sub-pixel, ADR-0037 decision 6).

## History

- 2026-10-15: filed when the whispering bubble took its direction from its first letter.
