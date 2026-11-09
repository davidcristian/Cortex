# A row named only by a code word cannot be kept

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

The forget reader in `forget_unnamed.py` reads no code word (`PIN`, `password`, `code`) as
naming a fact, so a message that names its fact only by one names no row. Unit calls on
2026-11-09, every row holding 7319: `Forget 7319 but keep my pin code.` keeps nothing and
lists the row `my card PIN is 7319`; `Forget my PIN 7319, keep everything else.` and `Forget
my bikelock-code 7319, keep everything else.` list every row; and `asks_to_keep` is false for
`my PIN is 7319` under `Forget my door code but keep my PIN.` and for `my Wi-Fi password is
7319` under `... keep the password.`, so that row counts as holding the number and the result
and `NUMBERS_LEFT_NOTE` ask to forget the number itself, which would delete the row kept.

## What to do

1. Write the messages above as tests first, beside `Forget 7319.` and `Forget the code 7319.`,
   which still ask for every row.
2. Let a keep clause's specific code word (`pin`, `password`, `Postleitzahl`, not `code` or
   `number`) name the rows that hold it, and keep every row when a clause keeps the rest and
   the forget part names none, then replay every recorded forget string.

## History

- 2026-11-09: filed from unit calls in the third audit of the night (`probe4.py` and
  `probe6.py` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`).
