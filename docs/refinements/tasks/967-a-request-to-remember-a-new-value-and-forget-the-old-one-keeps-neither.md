# A request to remember a new value and forget the old one keeps neither

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-05

`Note that my phone number is now 0699000000, and delete the old one.` usually shows a card. The
approved card deletes the old row and the turn stays out of memory, so no row holds either number. No
row held the new value in 11 of 16 draws of this message and its locker code form
([rows](../../readings/forget-refused-on-remember.md#the-draws-2026-10-31), rows M01 and M02). What the
person loses is one message, and they still hold the value. `UNKEPT_CLAIM_NOTE` closes every such turn,
whatever the reply says ([draws](../../readings/claim-reader-replays.md#the-note-on-every-withheld-request-to-remember-the-draws-2026-10-31)).

## Why a typed rule does not keep the value

The turn stays out because its text may repeat what was forgotten, so a rule that stores it must show
the stored text holds no old value.

- The forget's own text does not show that. On 9 of 11 cards on 2026-10-31 it was a label the
  message also holds (`phone number`), and on 2 of 11 it was the old value; on 2026-11-05 it was the
  old value on 7 of 10 and the label on 3
  ([texts](../../readings/forget-no-match-on-remember.md#the-texts-of-the-forget-calls-on-a-new-value-2026-11-05)).
  A rule that stores when the text is absent from the message covers only the value texts, and the
  share of those moves from night to night.
- A message can hold both values: `My code changed from 7319 to 8426, forget the old one.` Comparing
  the digit runs of the deleted row with the message covers numbers only. A name or an address holds
  none, and telling a label from a value in one is not a literal check.
- The two errors differ in cost. Withheld wrongly, the person sends one more message and the note says
  so. Stored wrongly, a fact the person just approved deleting is back in memory and nothing shows it.

So the note is the correct result until the person can read what is stored.

## Design: a second card

After a round whose forget deleted a row, on a message `asks_kept` reads, the brain shows one more card
listing the person's own words up to the retraction: `Note that my phone number is now 0699000000`. An
approved card stores those words alone, through `caps.memory.record`, with no reply and no tool line,
and no note shows. A declined card stores nothing and the note shows as now. The card holds the
person's own text and never text the model wrote, so ADR-0075's reason for showing a card on a tainted
turn holds, and the person is the one reader who knows which value is old.

## What to do

1. For the second card, write the clause reader, near misses first: cut at the first retraction clause,
   and keep the words after it when the retraction comes first.
2. Call `Confirmer` outside `ToolDispatcher`. `ConfirmationRequest` names a tool call today, and the
   overlay's `ConfirmCard` shows `tool_name` as the card's title and each argument as a row, so the
   card is a request with a name and one `text` argument holding the person's words. Proposed name,
   a pick that stays the maintainer's: `keep_memory`, the verb `asks_kept` reads and the noun
   `forget_memories` ends with, so the two cards of one turn read as a pair. Alternatives:
   `remember_text`, the word people type most, and `record_memory`, the store's verb. None is used
   by a tool today.
3. Decide the deep phase, which reads the cortex's runs from the stored reply.
4. Write rows and a rule before any draw: M01, M02 and
   `My code changed from 7319 to 8426, forget the old one.`, where the card shows the old value and a
   declined card leaves no row with it.

## History

- 2026-10-31: filed from the rows of the check of refusing a forget call. Filed
  [R-969](969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md) from the draws of
  the fixed readers.
- 2026-10-31: the first step shipped. `UNKEPT_CLAIM_NOTE` now shows on every withheld turn whose message
  `asks_kept` reads and `asks_not_kept` does not, whatever the reply says, rather than on another reply
  wording, since widening `claims_kept` to "I've updated that" would also fire after a file edit. The
  [rule written before the draws](../../readings/claim-reader-replays.md#the-note-on-every-withheld-request-to-remember-rows-and-the-rule-2026-10-31)
  held.
- 2026-11-05: the premise holds in the code and in 10 draws of M02: every approved card deleted the
  old row, `memory_withheld` (`memory_claim.py`) kept each turn out, no row held either number, and
  every reply ended with the note. A typed rule over the forget's text still covers only the value
  texts, so the second card stays the design; step 2 now holds the proposed name.
