# The stored time note shows under a time named in another language

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-11

`STORED_TIME_NOTE` shows when a turn stored a time and `names_time_of_day`
(`brain/packages/core/src/cortex_core/schedule_claim.py`) finds no time of day in the reply. On
2026-11-11 it read none in four replies that name the stored time, so each would get a note it
does not need, now in the person's language:

| Reply | `names_time_of_day` |
| --- | --- |
| `Je vous rappellerai demain à 9h de vider le casier.` | false |
| `Rappel prévu pour **9h00** demain.` | false |
| `Te lo recordaré mañana a las 10.` | false |
| `Îți voi aminti mâine la ora 14.` | false |
| `Ich erinnere dich morgen um 9 Uhr.` | true |

The first two forms were recorded on the shared stack on 2026-11-10
([readings](../../readings/overlay-compound-request-flows.md#counts)). This reader errs toward
showing the note, the safe side, so the cost is an extra note, never a missed one.

## What to do

1. Write near misses first (a number that is not a time: `9 h de route`, `las 10 tareas`,
   `ora 14 din program`), then read an hour after `à`, `a las`, `a la`, `la ora` and `um`, and
   a bold or bare `9h00`.
2. Replay every recorded reply in `docs/readings/` through the old and new reader, with counts.

## History

- 2026-11-11: filed from R-999, whose notes are now written in the person's language. Probe
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot4/probe2.py`.
