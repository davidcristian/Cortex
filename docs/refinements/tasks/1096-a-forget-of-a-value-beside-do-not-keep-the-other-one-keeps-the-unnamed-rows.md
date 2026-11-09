# A forget of a value beside do not keep the other one keeps the unnamed rows

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`Forget 7319.` deletes every row holding 7319, but `Forget 7319 and do not keep the shed one.`
names the shed row, so `unnamed` in `forget_unnamed.py` keeps the bike row as one the message does
not name. The same holds for `ne garde pas celui du cabanon non plus`, `no guardes el del shed
tampoco` and `nu păstra nici pe cel de la shed`. The person asked for both rows to go, and the
reader fails toward keeping ([readings](../../readings/forget-keep-clause.md#second-audit-probes-2026-11-09)).

## What to do

Write these messages and near misses (`Forget 7319, the shed one.`, which names only the shed row)
as tests first. Then read a negated keep clause, or a word such as `either`, `too`, `non plus` or
`tampoco`, beside a value named alone as asking for every row holding it, and replay every
recorded forget string.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
