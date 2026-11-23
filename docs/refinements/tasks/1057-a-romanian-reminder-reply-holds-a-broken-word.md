# A Romanian reminder reply holds a broken word

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-11-23

One live turn of `Amintește-mi la ora 18 să scot gunoiul pentru colectarea de luni.` on the stack
cortex (gemma-4-12B, text only) replied `Am programat unKy memore pentru astăzi, la ora 18:00`,
where a Romanian word for a reminder (`un memento`) is broken. The schedule call and the item were
right.

On 2026-11-23 the cortex of today's compose defaults (engine build `b12375-9d25e0014`, the
multi-token-prediction drafter at length 3) drew that message and two other Romanian reminder
messages eight times each. 8 of 24 replies held a broken word, such as `amânterea`, `Scote` and
`unटेल przypomínání`, and 4 of the first message's 8 stored items read `Scote gunoiul`, which the
person reads when the reminder fires. Every draw called the schedule tool once at the time asked
([readings](../../readings/single-draw-recounts.md#a-romanian-reminder-reply-with-a-broken-word)).
The brain sends no sampling field, so the cortex samples at the settings its server reports in
`/props`: temperature 1.0, `top_k` 64, `top_p` 0.95, `min_p` 0.05.

## What to do

1. Write a rule, then draw the same 24 messages with a lower temperature and, separately, a higher
   `min_p`, each sent in the request, and count the replies and items holding a broken word. The
   rule also counts the forms of the repo's other cortex rows that the same setting can move.
2. Record which setting the rows support before any change to a default or a prompt.

## History

- 2026-11-08: filed from a live draw recorded in
  [the readings](../../readings/schedule-weekday-day-after.md#the-refusal-or-a-note-2026-11-08).
- 2026-11-23: counted. The form recurs in 8 of 24 replies over three messages and in 4 of 24 stored
  items, and the sampling settings are read; a comparison of two settings is the next step.
