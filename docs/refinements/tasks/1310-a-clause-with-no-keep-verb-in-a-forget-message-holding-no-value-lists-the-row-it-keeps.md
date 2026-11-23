# A clause with no keep verb in a forget message holding no value lists the row it keeps

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-23

Over a car row, a phone and a locker that all end in `4242`, in unit calls through
`ForgetChosenTool`, `Forget my cart, the phone stays.` with the call text `4242` lists the phone.
No stored request holds `cart`, the message holds no value, and the clause naming the phone holds
no keep verb. The same message with the value, `Forget my cart 4242, the phone stays.`,
keeps the phone. A value no stored row holds reads as no value: `Forget my cart 1234, the phone
stays.` with the call text `4242`, and `Forget my car 1234, the phone stays.` with the call text
`phone`, list the phone. That form is each of the 12 rows asked to keep that the 4,104 cases of
[the longer forget word readings](../../readings/forget-longer-word-beside-a-value.md) list.

Over 12,768 replayed cases in `~/.cache/cortex-run/2026-11-23/a1/` (`mk.py`, `p_start.json`,
`p_head.json`), the card lists 902 rows the message asks to keep, each in a message holding no
value and a forget word no stored request holds, each with the call text `4242`, and the same
902 before and after the forget changes of 2026-11-23. They are the forms `the phone stays.`,
`le casier reste.`, `el gimnasio se queda.` and `dulap rămâne.`; `der Spind bleibt.` is read.

## What to do

1. Write the four forms as tests first, each beside its form holding the value.
2. Read such a clause in a message holding no value as the card reads it beside a value, or
   decline with the count of rows the reading keeps that the message asks to delete.
3. Replay `mk.py` at the old and new tree: no row asked to keep listed.

## History

- 2026-11-23: filed from a replay of forget word pairs over the card.
