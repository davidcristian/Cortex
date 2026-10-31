# A request to remember a new value and forget the old one keeps neither

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`Note that my phone number is now 0699000000, and delete the old one.` usually shows a card. The
approved card deletes the old row and the turn stays out of memory, so no row holds either number. No
row held the new value in 11 of 16 draws of this message and its locker code form
([rows](../../readings/forget-refused-on-remember.md#the-draws-2026-10-31), rows M01 and M02). What the
person loses is one message, and they still hold the value, as long as the reply says so. `claims_kept`
and `claims_forgotten` read the replies' wording ([replay](../../readings/claim-reader-replays.md#a-new-value-and-the-old-one-2026-10-31)),
so of 5 such draws on the fixed readers 2 end with `UNKEPT_CLAIM_NOTE` and 2 say so themselves. The
fifth said "I've updated that for you. Your new locker code is 8426" with no note
([draws](../../readings/claim-reader-replays.md#the-readers-in-real-turns-2026-10-31)).

## Why a typed rule does not keep the value

The turn stays out because its text may repeat what was forgotten, so a rule that stores it must show
the stored text holds no old value.

- The forget's own text does not show that. On 9 of 11 cards it was a label the message also holds
  (`phone number`), and on 2 of 11 it was the old value. A rule that stores when the text is absent
  from the message covers 2 of 11.
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

1. Show `UNKEPT_CLAIM_NOTE` on every withheld turn whose message `asks_kept` reads and `asks_not_kept`
   does not, whatever the reply says, in place of another reply wording. Widening `claims_kept` to "I've
   updated that" would also fire after a file edit. The rule, written before any draw: draw M01 and M02
   3 times and R01 to R05 of the [forget refusal rows](../../readings/forget-refused-on-remember.md#rows-and-the-rule-2026-10-31)
   once. It ships when every M draw with no row holding the new value ends with the note and no R draw
   does. A reply that already says the value was not kept gets the note too, which is true.
2. For the second card, write the clause reader, near misses first: cut at the first retraction clause,
   and keep the words after it when the retraction comes first.
3. Call `Confirmer` outside `ToolDispatcher`. `ConfirmationRequest` names a tool call today, so the
   card needs a name a person reads, which is a naming proposal under AGENTS.md.
4. Decide the deep phase, which reads the cortex's runs from the stored reply.
5. Write rows and a rule before any draw: M01, M02 and
   `My code changed from 7319 to 8426, forget the old one.`, where the card shows the old value and a
   declined card leaves no row with it.

## History

- 2026-10-31: filed from the rows of the check of refusing a forget call. Filed
  [R-969](969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md) from the draws of
  the fixed readers.
