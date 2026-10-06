# The preview of a failed turn has no tint

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0036](../../adr/ADR-0036-window-edge.md) decision 11
**Trigger:** a History line in this file recording the maintainer's pick of tint A, B or C.
**Verified:** 2026-10-06

A turn that fails while the overlay is minimized raises the preview, which shows the error, has no
countdown bar and stays until it is clicked or dismissed (`previewStays` in
`body/app/src/overlay/turnState.ts`, and [overlay UX](../../design/overlay-ux.md) section 4).
Nothing tints that card: the error is written in `--text` on the Lucid glass, while in the panel
the same error is a bubble washed in `--halt` at 14% (`.b-error` in `body/app/src/overlay.css`).

## Proposal

The card has no fill of its own (ADR-0036 decision 11): its whole face is the Lucid edge's glass,
with the text lifted above it. So the tint is a choice of where the colour goes, judged by eye in
both themes.

- **A. The error in `--halt`.** Only the text changes, to the red the stop and a chat row's trash
  take on hover. The glass and the edge stay as they are, and colour sits on the one line that went
  wrong.
- **B. A `--halt` wash over the glass** (recommended). The edge's glass for this card takes a
  `--halt` mix at the panel error bubble's 14%, and the text stays `--text`. A failure then looks
  the same in the preview and in the panel. It edits decision 11's "no fill" for a failed card.
- **C. The hairline in `--halt`.** The edge's crisp outline (`.edge-hair`) is drawn in `--halt`
  instead of `--stroke`, and the face stays neutral.

Each is one class on the card when `error` is set, plus its rule in `overlay.css` and a test that
the class follows the error.

## History

- 2026-10-06: filed when the failed turn's preview was made to show its error and stay up; the
  tint is a visual pick, so it waits for the maintainer.
