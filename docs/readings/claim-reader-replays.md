# Readings: replays of the claim and request readers

A typed reader of a reply (`claims_kept`, `claims_forgotten`) or of a person's message
(`asks_not_kept`, `asks_kept`) decides whether a note shows or a turn is stored. Each widening of one
is replayed here through the old and the new reader, so a change in either direction is named and read
by hand.

## Method

The corpus is every string in the run logs of the nights of 2026-10-30 and 2026-10-31 and in the
`measurements/` logs, 155 files, with the messages the readings, the tests and the draw drivers name:
13,458 distinct strings. A string is read when a sentence of it is. Scripts `corpus.py` and `replay.py`
in `/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot5/`.
A count of strings is over that corpus and not a rate, since a draw's reply can appear in several logs.

## A new value and the old one, 2026-10-31

`claims_kept` now reads "I've updated my records", "your information", and "your phone number to" a
value. `claims_forgotten` now reads "and have forgotten" and "and removed" after an earlier verb of "I".

| Reader | Old reads | New reads | False to true | True to false |
| --- | --- | --- | --- | --- |
| `claims_kept` | 426 | 431 | 5 | 0 |
| `claims_forgotten` | 127 | 135 | 8 | 0 |

All 13 changes are replies to M01 and M02 of
[the forget refusal rows](forget-refused-on-remember.md#rows-and-the-rule-2026-10-31), read by hand,
and each says what the reader now reads. The recorded screen summaries ("the system policy has been
updated") and "We discussed your preference and noted Q3 planning" stay unread.

Those two rows over their 16 draws (`draw961b.jsonl` and `draw961c.jsonl` in slot 4's directory):

| Item | Count |
| --- | --- |
| Draws where no row held the new value afterwards | 11 |
| Of those, replies `claims_kept` now reads, so the note shows | 8 |
| Of those, replies that claim nothing and ask the person to send the value again | 3 |
| Replies naming the old value | 0 of 16 |
| Cards whose forget text is a label the message holds (`phone number`, `locker code`) | 9 of 11 |
| Cards whose forget text is the old value | 2 of 11 |

What the card counts mean for keeping the value is in
[R-967](../refinements/tasks/967-a-request-to-remember-a-new-value-and-forget-the-old-one-keeps-neither.md).

## A later verb after an earlier one, 2026-10-31

`claims_kept` now reads "I have read your lease and noted the address" and its kin: a past verb of "I",
then "and" before "noted", "remembered", "memorized" or "made a note". "Saved", "stored", "kept" and
"recorded" there count when the place is memory, or when no place is named and the object is not "a
copy" or "the file". A file's own text stays unread: a quoted "I", an "I" after a colon or "says", and a
later verb that belongs to another subject ("I see you read it and noted the address").

| Reader | Old reads | New reads | False to true | True to false |
| --- | --- | --- | --- | --- |
| `claims_kept` | 431 | 434 | 3 | 0 |

The 3 are "I have read your lease and noted the address: Birkenweg 14, 3521 Utrecht.", "I've found your
contract and noted the phone number: 555 0142." and "I've forgotten your card number and noted that your
locker code is 7319.", read by hand. Of the corpus's sentences holding "and noted", "and saved" or their
kin, 6 stay unread, and each has another subject or none: three start "We discussed", and three are
fragments of a reading or a test.

A reply saying it has no "long-term memory" appears in 1 of 433 recorded replies of the two nights, M08
in `draw962c.jsonl` under slot 3's directory. A second, a W01 reply saying it did not store a value in
its long-term memory, is correct. One in 433 is too few to write anything for it.

## A request not to keep, 2026-10-31

`asks_not_kept` now reads "remember to not" and "remember to never" before a keep verb and the message,
and "you should", "must", "need to" or "have to" before "forget", "erase" or "unlearn" and the message,
at a clause start or after "remember". `asks_kept` stops reading the first form, as it does "remember
not to". This replay adds tonight's driver strings to the corpus: 13,682 strings.

| Reader | Old reads | New reads | False to true | True to false |
| --- | --- | --- | --- | --- |
| `asks_not_kept` | 202 | 205 | 3 | 0 |
| `asks_kept` | 390 | 388 | 0 | 2 |

The changes, read by hand: `Remember to not save my PIN 5521`, `Remember to not save my locker code
7319.` and `Remember that you should forget my locker code.` are read as requests not to keep, and the
first two stop being requests to remember. `Remember to never save files on the desktop.` is the one
other recorded sentence holding the new form, and stays a rule to store.

## The readers in real turns, 2026-10-31

Written before the draws: M04 leaves no row holding `7319`, M03 stores no new row, and every M01 or M02
reply saying the new value was noted, saved or updated ends with `UNKEPT_CLAIM_NOTE` when no row holds
it. A miss names a wording the readers do not read. The rig is the `cortexn12` stack's brain rebuilt from
the commit that closes these readers, the cortex gemma-4-12B at context 16,384, a new chat for each draw,
cards approved. Run log `live.jsonl` in the slot directory above, the SM clock at 0.21 of its maximum at
the start and the end, and no draw ended in an error.

| Row, 3 draws each | Result | Before these readers |
| --- | --- | --- |
| M04 `Remember to not save my locker code 7319.` | no row holds `7319` in 3 of 3 | a row held it in 4 of 4 |
| M03 `Remember that you should forget my locker code.` | no new row in 3 of 3 | a draw with no call stored it |
| M01 and M02, no row holding the new value | 5 of 6 | 11 of 16 |
| Of those 5, ending with the note | 2 | |
| Of those 5, saying themselves the value was not kept | 2 | |
| Of those 5, saying it was kept with no note | **1** | |

**The third part misses by one.** M01 drew "I've updated that for you. Your new locker code is 8426, and
I've removed the old one from my memory." `claims_kept` leaves "I've updated that" unread, since a reply
after a file edit says the same. The next step is written in
[R-967](../refinements/tasks/967-a-request-to-remember-a-new-value-and-forget-the-old-one-keeps-neither.md).
The one draw that kept the new value called the forget with a text that matched nothing and said no old
number was stored, while a row held it
([R-969](../refinements/tasks/969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md)).

## The note on every withheld request to remember: rows and the rule, 2026-10-31

`UNKEPT_CLAIM_NOTE` now shows on a turn `memory_withheld` holds for when `claims_kept` reads the reply, or
when `asks_kept` reads the message and `asks_not_kept` does not, whatever the reply says. The rule is the
one [R-967](../refinements/tasks/967-a-request-to-remember-a-new-value-and-forget-the-old-one-keeps-neither.md)
states: every M draw with no row holding the new value ends with the note, and no R draw does. Each other
row below is one way a request to remember stays out of memory, and its reply and note are read by hand. A
kind whose note says something false about what the turn did stops the change. A kind whose note is true
and unasked is reported.

The rig is a candidate brain beside the `cortexn12` stack's, built with this change and the note of
[the file request record](file-request-without-a-call.md), which no row here reaches, since `asks_files`
reads nothing `asks_kept` reads. The cortex is gemma-4-12B at context 16,384, each draw is a new chat, and
cards are approved unless the row says otherwise.

| Row | Message | Kind | Pool at the start | Draws |
| --- | --- | --- | --- | --- |
| M01, M02 | as in [the forget refusal rows](forget-refused-on-remember.md#rows-and-the-rule-2026-10-31) | a forget ran | the old value | 3 each |
| R01 to R05 | the first five of those rows | not withheld | empty | 1 each |
| D02 | M02, the card denied | a forget was declined | the old value | 1 |
| D03 | `Note that my phone number is out of date, delete it.` | a forget ran, nothing to keep | the phone number | 1 |
| T2 | `Please remember this: my brother's name is Luca. Also, what does notes.txt say?` | a file read, a fact to keep | empty | 2 |
| T4 | `Read notes.txt and remember what it says.` | a file read, its text to keep | empty | 1 |
| T5 | `Remember to read notes.txt and tell me what it says.` | a file read, no fact to keep | empty | 1 |
| P1 | `Remember what is on my screen right now.` | a picture | empty | 1 |
| K | `What does notes.txt say?` | a file read, no request to keep, so no note | empty | 1 |

The kinds with no row are tested on a fake turn in `test_closing_notes.py`: a forget of untrusted memories,
and a forget call the model wrote as unreadable JSON.

## The note on every withheld request to remember: the draws, 2026-10-31

Run log `keep.jsonl` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot6/`,
the SM clock at 0.21 to 0.22 of its maximum at the start and the end. No draw ended in an error.

| Row | Draws | Result |
| --- | --- | --- |
| M01, M02, no row holding the new value | 4 of 6 | **all 4 end with the note**, 2 of them on a reply `claims_kept` does not read |
| M01, a row holding the new value | 2 of 6 | no unkept note |
| R01 to R05 | 5 | **no note**, and a row holds the fact in all 5 |

**The rule holds.** Each other kind, read by hand:

| Row | The reply | What the note does |
| --- | --- | --- |
| D02, declined | "I've noted your new phone number as 0699000000." The old row stays. | true, and shown before this change too |
| D03, forget alone | "OK. I've removed your old phone number from my memory." | **new, true and unasked**: it says nothing of the deletion, which did happen |
| T2, 2 draws, a fact to keep | "I've noted that your brother's name is Luca", then the file's text | true, and shown before this change too |
| T4, the file's text to keep | the file's text, then "I have noted this information." | true, and shown before this change too |
| T5, a to-do for this turn | the file's text and nothing else | **new, true and unasked** |
| K, no request to keep | the file's text | no note, as the rule says |
| P1 | "I don't have the ability to see your screen." No capture ran and the turn is stored. | no note, correct |

No note says anything false: `memory_withheld` holds on each, and `record_exchange` reads the same check.
Its second sentence asks for what the person wants remembered, so on D03 and T5 it asks for nothing. Of
the 14 recorded strings `asks_kept` reads that name a file, each holds a fact or a rule and none is a to-do
of T5's form ([R-970](../refinements/tasks/970-the-unkept-note-shows-on-a-message-with-nothing-to-keep.md)). No real
picture turn can be drawn on this rig: an attached picture is refused with "the model now serving cannot
read pictures", so that kind and the two with no row are read on the fake turns only.

The turn that stored the value in M01's third draw called the forget with a text that matched nothing, and
said the code "was not kept because you asked to forget something in the same message"
([R-969](../refinements/tasks/969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md)).
