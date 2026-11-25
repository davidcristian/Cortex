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

1. Look for a message where `_held` alone keeps a row the message asks to keep; write each one
   found as a test that fails without `_held`.
2. If none is found, remove `_held`, record the 64 rows as deleted where the message asks, and
   draw it live with the rows seeded before it ships, since the card then lists more rows.

## History

- 2026-11-25: filed by the audit of the night's forget commits.
