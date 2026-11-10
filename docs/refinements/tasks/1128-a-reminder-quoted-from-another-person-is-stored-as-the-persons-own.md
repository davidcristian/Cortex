# A reminder quoted from another person is stored as the person's own

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-10

On 2026-11-10 at 06:32 to 06:35 local, on the shared stack (gemma 12B cortex), `Anna said:
"remind me every day at 8 to water the plants". Can you note that she likes plants?` stored a
daily reminder at 08:00 for the person in 4 of 4 draws: chats `s17-m5`, `s17-m5-2` and `s17-m5-3`
through the driver and one on the Linux shell
([readings](../../readings/overlay-mentioned-words-flows.md)). The person asked only to note that
Anna likes plants. Each reply said a daily reminder was set, and the first ended with
`DAILY_STORED_NOTE`, so no note was false, but none said the reminder came from words the person
quoted, and the reminder fires every morning until the person cancels it.

No typed reader looks at quotation marks around a request to remind. A refusal of
`schedule_task` beside a quote would move against that refusal's safe direction, which keeps the
tool, since `"Remind me at 8," I told myself.` and `Remind me to answer Anna's "call me at 8"`
are the person's own requests.

## What to do

1. Write near misses as tests first: a request outside the quote (`Remind me at 8 to "water the
   plants"`), the person quoting themself, a quote holding no request to remind, a quote in
   another language (`« rappelle-moi »`, `„erinnere mich“`). Replay every readings string.
2. Build a note the brain appends after a turn whose `schedule_task` call succeeded while every
   request to remind in the message stands inside quotation marks, naming the reminder stored.
   Its safe direction is to show; it must not invite a cancel in a text the model reads.
3. Draw the message above at least eight times on the old and new build and count the notes.

## History

- 2026-11-10: filed from the mentioned-words flows.
