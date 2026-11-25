# The call text check of a row word up to the first forget clause keeps only rows asked to delete

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`_held` (`forget_clauses.py`) reads a call text made of row words only up to the first clause
holding a forget verb, so `Forget my phones 1234, the phone stays.` with the call `phone` keeps the
phone. Since `_kept_later` (`forget_permit.py`) reads the clauses after the first forget clause,
`_held` changes no test: with it reverted, all 3,781 forget tests of `brain/packages/core` pass.
Over the replay sets it keeps 64 rows and no row asked to keep: 52 in the generator (12 labelled
asked to delete and 40 unlabelled list items, as `Forget 4242, the card, the phone stays.` and
`Forget the card 4242, the phone and the locker too.` with the call naming that row) and 12 in the
mixed messages. Counts in `~/.cache/cortex-run/2026-11-25/a1/gen/` (`*_fix.json` against
`*_noheld.json`).

## What to do

1. Remove `_held`, count the rows the card then deletes where the message asks (the 64 above and
   the 1,230 of the search below), and draw it live with the rows seeded before it ships, since
   the card then lists more rows.

## History

- 2026-11-25: filed by the audit of the night's forget commits.
- 2026-11-25: searched for a message where `_held` alone keeps a row the message asks to keep,
  and found none. The search: 21,996 messages from the rows' own words in five languages whose
  call (the noun, the phrase, or the noun and value) names a row word only in a clause after the
  first forget clause, beside a keep, stays, but, except or not clause for another row, as in
  `Forget it 4242, the card 4242, the locker stays.`. With `_held` and with it reverted the card
  lists no row asked to keep, and `_held` keeps 1,230 rows asked to delete that the reverted
  check deletes. The audit's generator, forget of everything, mixed and negation sets show no
  difference on a row asked to keep either (`search.py`, `held.py`, `held.log` in
  `~/.cache/cortex-run/2026-11-25/x1/held/`). `_held` stays until the seeded draw.
