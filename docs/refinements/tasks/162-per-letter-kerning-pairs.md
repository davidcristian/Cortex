# Per-letter boxes giving up kerning pairs

**Status:** open, fix when it bites
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Trigger:** The overlay adopting a licensed face, which reads in the tree as `--font` in
`body/app/src/overlay.css` naming anything other than the system stack it declares today
(`-apple-system, "Segoe UI", system-ui, "Helvetica Neue", sans-serif`), or as any `@font-face` rule
under `body/app/`, of which there are none today.
**Verified:** 2026-09-17

A whispered message's letters are one box each
inside an unbreakable word box (ADR-0037 decision 6), so kerning inside a word is lost while
that message's DOM is on screen (it re-renders plain only when its chat is next loaded).
Checked by eye at 13.5px in the system stack in both themes and invisible there. Trigger:
the overlay adopting a licensed face (overlay-ux.md §2 leaves that option open), whose kerning
is worth re-checking against a settled reply's plain rendering side by side.
Placed here 2026-07-21.

## Trail

- 2026-07-21: Joined the fix-when-it-bites bucket when the streaming redesign landed, recorded there
  as kerning pairs lost across the letter spans.
- 2026-09-11: read against the tree and not fired. `--font` in `body/app/src/overlay.css` is still
  the system stack, the stylesheet declares no `@font-face` and imports nothing, and section 2 of
  `docs/design/overlay-ux.md` still names a licensed sans as an option left open rather than a choice
  made. The letter DOM is as described: `components/WhisperBubble.tsx` still renders one span per
  letter inside aria-hidden word boxes and keeps that DOM after settling, so nothing re-kerns until
  the chat is next loaded. The whisper suite's 41 tests pass (`npx vitest run src/whisper`).
- 2026-09-17: read against the tree and not fired, and the trigger restated as the two readings
  that decide it. No commit since 2026-09-11 touched the stylesheet's font token or the letter DOM:
  the one change to `overlay.css` in that time rewrote a comment about the liquid edge. `--font` is
  still the system stack, no `@font-face` rule exists under `body/app/` outside its build and
  dependency directories, and section 2 of `docs/design/overlay-ux.md` still leaves a licensed sans
  open. `components/WhisperBubble.tsx` still renders the streaming or once-streamed message through
  `LiveWhisper`, one span per letter inside aria-hidden word boxes. The whisper suite's 41 tests
  pass (`npx vitest run src/whisper`).
