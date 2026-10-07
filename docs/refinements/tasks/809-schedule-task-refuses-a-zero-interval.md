# schedule_task refuses a zero interval

**Status:** open, waiting for its trigger
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** the row below has been drawn and its count written in this file's History.
**Verified:** 2026-10-07

`schedule_task` reads `every_seconds` in `_parse_every`
(`brain/packages/core/src/cortex_core/schedule_args.py`), which refuses any value outside 60 to
315360000, so `0` comes back as "'every_seconds' must be a number between 60 and 315360000". The
tool's schema says "omit for one-shot" and sets `minimum` to 60. `edit_scheduled` reads the same
`0` as "stop repeating" (`schedule_verb_args.py`). On 2026-10-07 one of nine one-shot reminder
requests to the cortex sent `every_seconds: 0` in its first `schedule_task` call, the request
whose text was markup. The refusal cost a second inference pass, and the retry without the field
succeeded ([readings](../../readings/body-actions-linux.md#the-interval-on-a-one-shot-reminder)).

## Proposal

- **A. Read `0` as a one-shot** (recommended if the row repeats it), the way `edit_scheduled`
  reads it as no repeat, with the schema's minimum and description saying so.
- **B. Name the fix in the refusal**: "omit 'every_seconds' for a one-shot reminder". It keeps the
  retry and makes it certain.

## The next row, and the rule it is read by

Twenty one-shot reminder requests, ten whose text holds markup or quotes and ten plain, each in a
fresh session through `BrainService.Converse`, with the cortex at its shipped settings and
`CORTEX_SCHEDULE_BACKEND=redis`. Count the first `schedule_task` calls that send `every_seconds`.
Two or more of twenty: build A with tests. None or one: decline, since a single refusal costs one
retry the cortex already makes.

## History

- 2026-10-07: filed from the Linux shell's reminder pushes, where the one refused call was seen.
