# Per-letter boxes giving up kerning pairs

**Status:** open, fix when it bites
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Trigger:** The overlay adopting a licensed face.

A whispered message's letters are one box each
inside an unbreakable word box (ADR-0037 decision 6), so kerning inside a word is lost while
that message's DOM is on screen (it re-renders plain only when its chat is next loaded).
Checked by eye at 13.5px in the system stack in both themes and invisible there. Trigger:
the overlay adopting a licensed face (overlay-ux.md §2 keeps that door open), whose kerning
is worth re-checking against a settled reply's plain rendering side by side.
Placed here 2026-07-21.

## Trail

- 2026-07-21: Joined the fix-when-it-bites bucket when the streaming redesign landed, recorded there
  as kerning pairs lost across the letter spans.
