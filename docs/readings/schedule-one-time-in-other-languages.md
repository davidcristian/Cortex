# Readings: a one-time time with no day, in five languages

Whether a request for one reminder at a time of day, with no day named, is stored once or as a
daily repeat, and whether a reply over a daily store says that it repeats. The request is written
in English, German, French, Spanish and Romanian. A daily store comes from `schedule_task` with
`at_time` and no day selector; its result ends with `_DAILY_NOTE`
(`brain/packages/core/src/cortex_core/schedule_tools.py`), a note the model reads. Scheduling is
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md).

## The rig

**2026-11-07**, the `cortexn15` GPU stack of that night, as in
[overlay-language-and-locale-flows.md](overlay-language-and-locale-flows.md#the-rig): gemma-4-12B
at a context of 16,384 tokens, schedules on Redis in `Europe/Berlin`, the brain's clock on Saturday
7 November before 17:30. Each build runs as a second brain on the stack network whose model
requests go through the recording proxy: the baseline from a `git archive` of the tree before the
change, the candidate from the tree with it. Every draw is a new chat with every card approved. Before
each draw the `memories` rows naming that row's subject are deleted, so no draw recalls an earlier
one. After each draw a script reads the chat's `cortex:schedule:*` records, then deletes them, so
the schedule never fills and no repeat is read as already stored. Scripts and run logs:
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot10/`.

## Rows and the rule, written before the first draw

| Row | Request | Draws |
| --- | --- | --- |
| E | `Remind me at 17:30 to call the plumber.` | 3 |
| D | `Erinnere mich um 17:30 Uhr an die Wäsche.` | 3 |
| F | `Rappelle-moi à 17h30 d'appeler le plombier.` | 3 |
| S | `Recuérdame a las 17:30 llamar al fontanero.` | 3 |
| R | `Amintește-mi la 17:30 să sun instalatorul.` | 3 |

Each draw is read as one of four outcomes, from the chat's records at the end of the turn and the
reply text the model wrote (before any note the brain appends):

- **once**: every item the chat holds is a one-shot, including one a daily store became through
  `edit_scheduled` with `every_seconds` 0 in the same turn;
- **daily, said**: an item repeats every day and the model's text says it repeats;
- **daily, silent**: an item repeats every day and the model's text does not say so. This is the
  form the candidate is for;
- **no item**: the turn stored nothing.

A draw passes when it is once, daily said, or daily silent with the brain's note appended. The
form's frequency (daily silent per row) is counted for each build as its own figure and is not a
pass item: the candidate changes only text appended after the reply, so it cannot change the
model's call, and the first model requests of both builds are compared to confirm it.

**Pass rule for the candidate** (a brain-appended note after a typed check that the stored rule
repeats every day and the reply names no repeat):

1. In every candidate draw where the form occurs, the note is appended.
2. No candidate draw outside the form gets the note: not a once draw, and not a daily draw whose
   text says it repeats in its own language.
3. The first model request of a candidate draw matches the baseline's for the same row, apart
   from ids and times.
4. If the form does not occur in the candidate's draws, the decision is a replay: every recorded
   reply of this night with a daily or one-time `schedule_task` call (this record's draws of both
   builds and the English and German rows in
   [overlay-language-and-locale-flows.md](overlay-language-and-locale-flows.md)) goes through the
   candidate's check with its recorded calls. The candidate ships if the check selects every
   daily silent reply, at least the German one recorded that night, and no other.

Notes the brain appends are English under any reply
([R-999](../refinements/tasks/999-a-note-the-brain-appends-is-english-under-a-reply-in-another-language.md)).
The candidate does not change that; this record says how its note reads under each language.

**Second condition, written after the first candidate run and before any run under it.** Item 3
cannot hold as written: the first requests of the first runs differ in the recalled-memory block,
because a draw recalled the exchanges of the other rows' earlier draws. Under the second condition
the `memories` rows of all five subjects are deleted before each draw, and item 3 compares the
first requests outside the recalled-memory block, apart from ids and times. The other items stay
as written.

## Results

SM clock during the draws: 0.52 to 0.57 of `clocks.max.sm`. Each cell counts draws of three;
"edited" is a daily store made one time by `edit_scheduled` with `every_seconds` 0 in the same
turn, counted as once. "Held" is a call that matched slot 8's daily `Wäsche` item from another
chat, left on the schedule, so no item was added and the result had the daily note.

| Build | Row | Once | Daily, said | Daily, silent | No item |
| --- | --- | --- | --- | --- | --- |
| baseline | E | 3 (1 edited) | 0 | 0 | 0 |
| baseline | D | 2 | 1 (held) | 0 | 0 |
| baseline | F | 3 | 0 | 0 | 0 |
| baseline | S | 2 (1 edited) | 1 | 0 | 0 |
| baseline | R | 1 | 2 | 0 | 0 |
| candidate, first | E | 1 | 1 | 0 | 1 |
| candidate, first | D | 1 | 2 (both held) | 0 | 0 |
| candidate, first | F | 0 | 1 | 1, note appended | 1 |
| candidate, first | S | 1 | 2 | 0 | 0 |
| candidate, first | R | 2 (1 edited) | 1 | 0 | 0 |
| candidate, second | E | 3 (1 edited) | 0 | 0 | 0 |
| candidate, second | D | 2 | 1 (held) | 0 | 0 |
| candidate, second | F | 2 | 0 | 1, note appended | 0 |
| candidate, second | S | 2 | 1 | 0 | 0 |
| candidate, second | R | 2 (2 edited) | 0 | 1, note appended | 0 |

The form occurred once in 30 draws: the French candidate draw `C'est fait, j'ai programmé un
rappel pour "Appeler le plombier" aujourd'hui à 17h30.` over a daily item, which got the note.
Every daily, said reply named the repeat in its own language (`în fiecare zi`, `todos los días`,
`täglich`, `täglichen`, `tous les jours`, `wiederholt sich jeden Tag`, `every day`), and none got
the note. No once draw got it. Of the first runs, items 1 and 2 hold. Item 3 does not hold as
written: no pair of first requests is equal, and all 15 are equal outside the recalled-memory
block. Four candidate first requests after the French draw recalled its stored exchange with the
note. The replay of item 4 selects the French draw and slot 8's German reply
`OK, ich habe dich für 17:30 Uhr an die Wäsche erinnert.` and no other of the 32 replies.

Under the second condition the form occurred twice in 15 draws, the French
`C'est fait ! Je vous rappellerai d'appeler le plombier aujourd'hui à 17h30.` and the Romanian
`Am programat un întunecire pentru astăzi la orele 17:30 [...]`, both over a daily item, and both
got the note. The two daily, said replies (`wiederholt sich täglich`, `todos los días`) and the
eleven once draws did not. All 15 first requests equal the baseline's outside the
recalled-memory block, and none recalls the note. Every item holds, so the candidate passed its
rule and ships. Across all 45 draws the form occurred 3 times, each in the candidate, where the
model reads the same requests as in the baseline; its frequency is draw noise at this count.

Two first-run candidate draws stored nothing. The French one made only a `list_scheduled` call
and replied `D'accord, j'ai bien noté votre rappel pour appeler le plombier à 17h30.`, a claim
`claims_scheduled` does not read, since it reads English forms
([R-999](../refinements/tasks/999-a-note-the-brain-appends-is-english-under-a-reply-in-another-language.md)).
The English one listed the schedule and asked whether to add the reminder.

The note is English under a reply in any language. Under the French draw it reads
`C'est fait, j'ai programmé un rappel [...] aujourd'hui à 17h30.` followed by
`(This reminder repeats every day. Ask to make it one time if you meant only once.)`.
