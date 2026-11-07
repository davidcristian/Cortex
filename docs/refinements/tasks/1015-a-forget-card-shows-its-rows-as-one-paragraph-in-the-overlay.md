# A forget card shows its rows as one paragraph in the overlay

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

The `forget_memories` card is one string with a line per row: a heading, a `- ` line per row the
text matched, and for rows listed by value a line `Listed because they also hold 7731:` before
them. The dispatcher sends that string as the `reason` of the `ConfirmRequest`
(`_confirmed` in `dispatch.py`), and `ConfirmCard.tsx` renders it in `<p className="confirm-reason">`.
The `.confirm-reason` rule in `overlay.css` sets no `white-space`, so the browser folds every line
break into a space: the rows, and the line that says which rows were listed by value, run together
as one paragraph. `.confirm-raw` and `.confirm-row dd` already set `white-space: pre-wrap`.

## What to do

1. Write a Vitest case in `ConfirmCard.test.tsx` that renders a reason with two lines and asserts
   the element's computed `white-space` keeps the break, or render each line as its own element.
2. Set `white-space: pre-wrap` and `overflow-wrap: anywhere` on `.confirm-reason`, then show a
   forget card with a row listed by value on the real Linux shell and grab a frame, denying the
   card so no stored row is deleted.

## History

- 2026-11-07: filed while marking the rows a forget card lists by value; the overlay was not
  driven to a card in that pass.
