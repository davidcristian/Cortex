# Open-chat header title consistency

**Status:** landed 2026-07-16
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

Opened 2026-07-16 behind the landed titles above. The
switcher now shows the brain title (`SessionSummary.title`), but opening that chat re-derives the
header from the loaded first user message (`deriveTitle`/`titleFor` in `sessionState.ts`), so the
header and the switcher row can disagree. `GetSessionMessages` carries messages, not a title, so
unifying them needs a `title` on that read path (a proto field + overlay plumbing), which a
brain-contained change cannot deliver. Note the smaller alternative first: the overlay could
carry the switcher's title into `openSession` when the user picks a row, covering the open path
without a proto change, but not cold-start adoption or cycling, which load by id.
**Landed 2026-07-16 as the overlay-only carry ([ADR-0021 header-title addendum](../../adr/ADR-0021-session-read-seam.md)),
and both this entry and the index undersold that option.** The header no longer re-derives
locally: `openSession` and `adoptSession` read the chat's title from the already-loaded
`state.sessions` (the same `SessionSummary.title` the switcher row renders) when the chat is in
the list, falling back to the first-message derivation only when it is not (`headerTitle` in
`sessionState.ts`). Header and switcher now read one `sessions` snapshot, so they are equal by
construction, a stronger guarantee than the proto field: a `title` on `GetSessionMessages` is a
second read that a title change between it and `ListSessions` could desync, and it is more surface
across four trees for a case the user cannot see (below). The carry closes three disagreements the
entry named only one of: a user **rename** (default on, always visible, landed the same day) whose
label the header ignored; a **truncation-length** gap (the brain bounds to `TITLE_MAX` 48, the
overlay's `deriveTitle` to 32, so a 33-to-48-char first message read longer in the switcher than
the header); and a **generated title** (behind `CORTEX_GENERATE_TITLES`). The entry's claim that
the carry misses "cold-start adoption or cycling, which load by id" is wrong read against the code:
adoption targets `sessions[0]` and cycling targets `cycleTarget(state.sessions, ...)`, so both
already target a session in `state.sessions`; doing the lookup in the reducer (not threading the
clicked row's title through the click handler, the narrower shape the entry imagined) covers
switcher-open, cycling, and adoption alike. Gated at 100% over fakes, with the carry
mutation-proven (reverting `headerTitle` to the local derivation makes the switcher-title tests
in `openSession`, `adoptSession`, and the cold-start hook fail); browser-validated against the demo
bridge, live-validated against real Redis (below).
**The truncation-length third of that claim was itself too broad, and closed 2026-08-03
([ADR-0021 truncation addendum](../../adr/ADR-0021-session-read-seam.md)).** The carry closed the
gap for a chat being *loaded*, which is the only kind `headerTitle` sees. It left it open for the
chat being *had*: `turnState.submit` names a brand-new chat from `deriveTitle` in the same render
that starts its first turn, and never revisits that header, so the 32 bound survived on the one
path where the overlay has no brain title to read. The turn-completion refresh then lists the
chat, and from that moment the header and that chat's own switcher row are two renderings of the
same first message. Measured in Chromium at 900x900 with the demo bridge extended to list a
submitted chat the way the brain does: a 42-character first message read in full in the row and
as `How does the session title trunc…` in the header, both visible together, in a header box of
339px that fits 42 characters against the row's 314px that fits 39, so the shorter bound was not
answering less room. The overlay's `TITLE_MAX` is now 48 and `scripts/crosscheck.py` holds the
two declarations equal, the pair being that gate's third entry and the first in TypeScript.

## Trail

- 2026-07-16: The item landed as the overlay-only carry and opened one entry behind it. The
  index reads the carry as a stronger guarantee than the `GetSessionMessages` title field,
  which would be a second read that a change between the two could desync.
- 2026-08-03: The truncation third was settled, found by the survey behind the cross-language
  constant scan rather than by a backlog entry; `TITLE_MAX` was already divergent at 48 against
  32 when that registry was built, so registering it then would have turned a gate on over a
  shipped disagreement nobody had decided how to resolve, and it waited on this decision rather
  than on the scanner. The overlay's bound is 48 now, the two declarations are the constant
  scan's third registered pair and its first in TypeScript, and the gate was proved to fail on a
  divergence before being trusted. The area count did not move, since this corrects a landed
  entry and narrows the residual below it rather than closing one or opening one.
