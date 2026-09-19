# Per-letter boxes losing kerning pairs

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)
**Trigger:** The overlay adopting a licensed face, which shows up in the tree as `--font` in
`body/app/src/overlay.css` naming anything other than the system stack it declares today
(`-apple-system, "Segoe UI", system-ui, "Helvetica Neue", sans-serif`), or as any `@font-face` rule
under `body/app/`, of which there are none today.
**Verified:** 2026-09-17

A whispered message puts each letter in its own box inside an unbreakable word box (ADR-0037
decision 6), so kerning inside a word is lost while that message's DOM is on screen. It renders as
plain text the next time its chat is loaded. Checked by eye at 13.5px in the system font stack in
both themes, where it is invisible. It would be worth checking again against a licensed face, which
`docs/design/overlay-ux.md` section 2 leaves open as an option.

## History

- 2026-07-21: Filed when the streaming redesign was committed.
- 2026-09-11: Checked; the trigger has not fired. `--font` is still the system stack and the
  stylesheet declares no `@font-face`. `components/WhisperBubble.tsx` still renders one span per
  letter inside aria-hidden word boxes and keeps that DOM after settling. The whisper suite's 41
  tests pass (`npx vitest run src/whisper`).
- 2026-09-17: Checked again; nothing has changed. The one commit to `overlay.css` since then
  rewrote a comment about the liquid edge. The trigger is now stated as the two readings that decide
  it.
