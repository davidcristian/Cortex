# A remark beside no whole row lists the row it names

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`_read` (`forget_inside.py`) reads row names from the asking part of a forget message (`asking`
in `forget_clauses.py`) only when that part names a row holding the call's text whole; otherwise
it reads the whole message, remarks included
([the remark reader](../../readings/forget-remark-about-the-value.md)). With the rows
`Remember that my card is 4111 1111 1111 4242.` and `Remember that my phone is 0721 555 4242.`,
the call text `4242` and the message `Forget the card 4242, the one I read from my phone.`, the
card lists and deletes the phone row, which only the remark names; no row holds `4242` whole. The
same holds for `Forget 4242 and my card, I sent the code from my phone.` beside the locker code,
the card and the phone. The person still sees the card before the delete.

## What to do

1. Write tests first: both messages above keep the phone row and show it in the kept note;
   `Forget 4242 that I texted from my phone.` beside the locker code and the phone keeps its
   current listing unless the change says why.
2. Read the asking part when it names any row holding the text, whole or as a group, and keep
   the whole message otherwise. A destructive card keeps rows when unsure.
3. Replay every recorded message and test string through the card; every change must keep a row.

## History

- 2026-11-13: filed while narrowing the kind word beside a remark, which left this form unchanged.
