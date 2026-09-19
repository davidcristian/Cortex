# The reserved rail is 6px only on one engine

**Status:** open, dead until a consumer
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 22, scrollbars as reserved chrome ([overlay-ux.md §2](../../design/overlay-ux.md))
**Trigger:** The overlay running on an engine without `::-webkit-scrollbar`, such as Gecko, since only such an engine takes the fenced branch.
**Verified:** 2026-09-19

Every scroll container holds
`scrollbar-gutter: stable` and funds the rail out of its own inline-end padding, either
subtracted from a padding big enough to hold it (`calc(16px - var(--rail))` on `.history` and
`.rows`, the whole 6px inset on `.switcher` and `.reminders`) or added beside it where there was
none to spend (`.thoughts-body`, `.confirm-draft`, `.field`). Every one of those numbers assumes
the reserved rail really is `--rail`, which holds wherever `::-webkit-scrollbar` sets the width
and nowhere else. Chromium honours the standards properties **over** the pseudo-elements when
both are set, so leaving them both unfenced would reserve a band the padding never accounted for:
measured 2026-07-20 on `.switcher`, the shipped fence gives a computed `scrollbar-width: auto`
and a 6px gutter, and adding `scrollbar-width: thin` alone takes the gutter to 10px and 4px off
the content width. The standards path is therefore fenced behind
`@supports not selector(::-webkit-scrollbar)`, where `thin` is whatever the UA says it is. On
those engines the subtraction does not balance and the inline-end margin reads a few px wider
than the other side. The property that matters survives (nothing moves when the bar appears,
because the gutter is reserved either way); what is lost is exact symmetry on an engine the body
does not run on. The fix, whenever one of them becomes a target, is to stop assuming the width
and measure it: a probe element read once at startup (`offsetWidth - clientWidth`) published back
as `--rail` makes every subtraction true on any engine, at the cost of a small module and its
tests, which is why it is not in a CSS-only slice.
- **Read against the tree and against the browser on 2026-08-03, when the chat floor's probe was
  built. The status does not move, and the recipe above needs one correction.** The small module
  now exists (`overlay/measured.ts`) and this entry could ride it, so what keeps it deferred is
  only what always kept it deferred: no non-Chromium engine runs the overlay. On the engine that
  does, the measurement is circular, `::-webkit-scrollbar { width: var(--rail) }` setting the very
  width a probe would read back, so publishing it writes 6px over 6px; the version that would help
  a fenced engine has to publish a SECOND property rather than the same one, or the webkit rule
  consumes its own output, and that is a change to every subtraction in the stylesheet rather than
  a line of wiring. The measurement was taken while the audit was on and confirms the assumption:
  `.history` and `.field` both reserve exactly 6px. The recipe is right only on a box with no
  border, which two of the containers it would serve have, so `.reminders` answers 8px for a 6px
  rail inside two 1px edges; whoever picks this up takes the borders off the reading first.

## Trail

- 2026-07-20: Measured on `.switcher` and filed when scrollbars became reserved chrome, the shipped
  fence giving a computed `scrollbar-width: auto` and a 6px gutter where adding `scrollbar-width:
  thin` alone takes the gutter to 10px.
- 2026-08-03: Re-read against the tree and against the browser when the chat floor's probe was
  built, and it stays rather than riding `overlay/measured.ts`. On the engine that ships the
  measurement is circular, so a fenced engine needs a second property and therefore a change to
  every subtraction in the stylesheet. `.history` and `.field` were confirmed at exactly 6px, and
  the recipe holds only on a box with no border.
- 2026-09-13: Re-derived and the premise is unchanged; only the pointers into the stylesheet
  moved. `--rail: 6px` is at `body/app/src/overlay.css:40`, the pseudo-element width that sets it
  at lines 146 to 148, and the standards fence at lines 202 to 206. All six funding shapes are
  still there: `calc(16px - var(--rail))` on `.history` (line 819) and `.rows` (line 1717), the
  6px inset on `.switcher` and `.reminders`, and a whole added rail on `.thoughts-body` (line
  1142), `.confirm-draft` (line 1304) and `.field` (line 1511). The trigger has not fired: the
  overlay still runs on WebView2 alone, so nothing reaches the fenced branch and the entry stays
  open.
- 2026-09-19: Re-derived. The premise holds and the trigger has not fired, since the Windows shell
  is still WebView2 and nothing else runs the overlay. Every stylesheet citation from 2026-09-13
  after line 300 was one line short from the day it was written, because the same commit added a
  line to the edge comment above them: the funding shapes sit at `body/app/src/overlay.css` lines
  820 (`.history`), 1718 (`.rows`), 1143 (`.thoughts-body`), 1305 (`.confirm-draft`) and 1512
  (`.field`), and the standards fence runs from line 202 to 207. The trigger named any engine that
  is not Chromium, which is wider than the case it guards: `@supports not
  selector(::-webkit-scrollbar)` is false wherever the pseudo-element exists, and WebKit, the
  engine a Tauri shell uses on Linux and macOS, is where it came from. So only an engine without
  it, Gecko being the one in use, reaches the unbalanced subtraction. Whether WebKit's gutter
  reserves exactly `--rail` under `scrollbar-gutter: stable` has not been measured. The
  stylesheet's own comment on this trade still named the rejected recipe, publishing the probe's
  reading as `--rail`, and gave ADR-0011 as the origin, which holds only a summary line pointing on
  to ADR-0035 decision 22; it now names the second property and ADR-0035.
