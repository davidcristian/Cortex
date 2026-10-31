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

So after this change no draw left the person believing the new value was stored. What the card counts
mean for keeping the value is in
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
