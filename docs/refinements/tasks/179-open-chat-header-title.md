# Open-chat header title consistency

**Status:** done 2026-07-16
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

The switcher showed the brain's title (`SessionSummary.title`), but opening that chat computed the
header again from the loaded first user message, so the two could disagree.

Fixed in the overlay alone. `openSession` and `adoptSession` read the chat's title from the
already-loaded `state.sessions`, the same `SessionSummary.title` the switcher row renders, falling
back to the first-message derivation only when the chat is not in the list (`headerTitle` in
`sessionState.ts`). Header and switcher now read one `sessions` snapshot, so they cannot disagree.
That is a stronger guarantee than the `title` field on `GetSessionMessages` the entry proposed,
which would be a second read that a title change between it and `ListSessions` could desync, and it
is less surface across four trees.

The fix closed three disagreements where the entry named one: a user rename, whose label the header
ignored; a truncation-length gap (the brain bounds to `TITLE_MAX` 48 and the overlay's `deriveTitle`
to 32, so a 33-to-48-character first message read longer in the switcher); and a generated title.
The entry's claim that it misses cold-start adoption and cycling is wrong: adoption targets
`sessions[0]` and cycling targets `cycleTarget(state.sessions, ...)`, so both already target a
session in `state.sessions`, and doing the lookup in the reducer covers all three paths.

The truncation gap was narrower still than that. The overlay fix closed it for a chat being loaded,
which is all `headerTitle` sees, and left it open for the chat being had: `turnState.submit` names a
brand-new chat from `deriveTitle` in the same render that starts its first turn and never revisits
that header. Measured in Chromium at 900x900: a 42-character first message read in full in the row
and as `How does the session title trunc…` in the header, in a header box of 339px that fits 42
characters against the row's 314px that fits 39, so the shorter bound was not answering less room.
The overlay's `TITLE_MAX` is now 48 and `scripts/crosscheck.py` checks the two declarations are
equal.

## History

- 2026-07-16: Closed as the overlay-only fix, opening one entry behind it.
- 2026-08-03: The truncation part was settled, found by the survey behind the cross-language
  constant scan rather than by a backlog entry. `TITLE_MAX` was already 48 against 32 when that
  registry was built, so registering it then would have turned a check on over a disagreement nobody
  had decided how to resolve. The two declarations are now the scan's third registered pair and its
  first in TypeScript, and the check was proved to fail on a divergence before being relied on.
