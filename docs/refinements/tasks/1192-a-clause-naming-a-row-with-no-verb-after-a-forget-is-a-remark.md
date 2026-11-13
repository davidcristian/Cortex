# A clause naming a row with no verb after a forget is a remark

**Status:** done 2026-11-14
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`asking` (`forget_clauses.py`) reads a clause holding no forget verb, keep clause or the call's
value as a remark unless it opens with `and`. `_grouped` (`forget_inside.py`) then lists no row
that only words outside the asking part name. With the rows `my locker code is 4242`, `my card is
4111 1111 1111 4242` and `my phone is 0721 555 4242`, the call text `4242` and the message `Forget
the locker code 4242 and the card, my phone as well.`, the phone row is kept although the person
asked for it. The same holds for `the phone too`, `also my phone`, `plus my phone`, `then my
phone`, `my phone included`, `even my phone` and a second sentence `My phone as well.`; the tree
before the remark change deleted the phone in each. This keeps a row, the safe direction, and the
kept note shows it, so the person can ask again.

## What to do

1. Write tests first from the messages above beside the remark tests of
   [the remark reader](../../readings/forget-remark-about-the-value.md).
2. Read a clause that names a kind of row and holds an adding word (`too`, `as well`, `also`,
   `plus`) as asking, written as a set the tests list. Keep rows when unsure.
3. Replay every recorded message and test string through the card; name every changed listing.

## History

- 2026-11-13: filed by the third audit of the night, with `slot14/c2.json` over `slot12/probe.py` as
  the reproduction, both in `/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/`.
- 2026-11-14: the remark reader now also reads the asking part beside a row holding the value only
  as a group, so beside a card and a phone ending `4242` the messages `Forget the card 4242, my
  phone as well.`, `Forget the card 4242, the phone one too.` and `Forget the card 4242. My phone
  as well.` keep the phone, which the tree before deleted. The fix asked for here covers them too.
- 2026-11-14: done. `asking` reads a clause that only adds a row as asking (`_adds`: `too`, `also`,
  `as well`, `plus`, `aussi`, `également`, `auch` or `ebenfalls` at one end, a word for the or my,
  then only fact words of rows holding the text), so `my phone as well`, `the phone too`, `also my
  phone`, `plus my phone` and a second sentence `My phone as well.` list the phone. `then my
  phone`, `my phone included` and `even my phone` stay remarks and keep the phone under the kept
  line. Neither draw of `Forget the card 4242, my phone stays.` deleted the card, and a brain
  note in each reply said nothing was deleted. The replay and the draws are in
  [the remark readings](../../readings/forget-remark-about-the-value.md#a-clause-adding-a-row).
