# A Romanian reminder reply holds a broken word

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-11-28

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

On 2026-11-25 the same 24 messages were drawn twice in each of three cells, the server's settings,
temperature 0.5 and `min_p` 0.2, each sent in every cortex request. Replies with a word that is
not Romanian read 6, 3 and 3 of 48, and items with one 4, 4 and 6 of 48, so no setting passed the
rule written first ([readings](../../readings/cortex-sampling-broken-words.md)). Every broken item
is M1's `Scote` or `Scoat` for `Scoate` (take out), written by the cortex in the call's `text`
argument, and neither setting removed it. A sent sampler would also move every cortex row that
readings record lists, and [ADR-0077](../../adr/ADR-0077-model-card-settings.md) decision 3 needs
those rows drawn before a tier's sampler moves.

## What to do

1. **The item.** A typed check of the item's `text` against the words of the person's message, by
   the rule written first in
   [the readings](../../readings/cortex-sampling-broken-words.md#a-typed-check-of-the-item-replayed-2026-11-27),
   flags all 18 broken items of the 167 recorded and 1 right one, the second person `Să scoți`, so
   it is not built. A rule that passes it reads every person and mood of the message's verb, which
   is a conjugation reader for each language. Write that rule with `Să scoți` among its near-miss
   rows and count it on items drawn after it is written, since a replay of the items it was
   written from shows nothing.
2. **The reply**, which is this task's defect. A check of the item reaches a reply only when the
   reply quotes the item, 8 of the 20 recorded replies with a word that is not Romanian. The
   other 14 hold the cortex's own word for a reminder, and 8 of those are written in Romanian
   letters, as is the first draw's `unKy memore`, so only a reader of Romanian words reaches them.
   A letter check by the rule written first in
   [the readings](../../readings/cortex-sampling-broken-words.md#a-letter-check-of-the-reply-the-rule-written-2026-11-28)
   marks 5 of the 6 recorded replies holding a letter outside the Romanian alphabet, 0 of the
   162 others and 0 of 17,280 true replies generated in five languages. The sixth called
   `edit_scheduled` after `schedule_task`, a turn the rule leaves unchecked because an edit can
   change the text and time a note restating the creation would name; the letters alone mark
   it. So the note is not built. The next rule keeps each item's text and due time by its id
   through the creation and edit results, with the edit result holding the edited text in a
   field the model does not read, as the cancel result does, and checks every turn whose calls
   are all scheduling calls. Write it first and count it on replies drawn after it, since the six
   recorded replies have now been read.
3. Leave the sampler as the file sets it unless a later row on another form calls for one.

## History

- 2026-11-08: filed from a live draw recorded in
  [the readings](../../readings/schedule-weekday-day-after.md#the-refusal-or-a-note-2026-11-08).
- 2026-11-23: counted. The form recurs in 8 of 24 replies over three messages and in 4 of 24 stored
  items, and the sampling settings are read; a comparison of two settings is the next step.
- 2026-11-25: drew the 24 messages twice at the server's settings, at temperature 0.5 and at
  `min_p` 0.2. No setting passed the rule; the broken items are one M1 form that no setting
  removed, so the next step is a typed check of the item text.
- 2026-11-27: replayed the 167 recorded items through a typed check of the item written first: it
  flags all 18 broken items and the right `Să scoți`, so it is not built. A check of the item
  reaches 8 of the 20 broken replies, the ones quoting it, so step 2 now names the reply's own
  remedy.
- 2026-11-28: replayed a letter check of the reply, by a rule written first, over the 168
  recorded replies and 17,280 generated true replies: it marks 5 of the 6 replies with a letter
  outside the Romanian alphabet and no other reply, so the note is not built, and step 2 names
  a note that stays true over an edit. Filed
  [R-1391](1391-a-spanish-message-quoting-two-english-list-words-gets-english-notes.md).
