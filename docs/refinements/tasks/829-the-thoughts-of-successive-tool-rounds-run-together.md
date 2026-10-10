# The thoughts of successive tool rounds run together

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0020](../../adr/ADR-0020-reasoning-status.md)
**Verified:** 2026-10-10

A turn that called four tools showed its `Thoughts` as one text with each round's reasoning
glued to the last one's final sentence: "Step 4: Extract links.The user wants me to read ...",
"... using the subject.The user wants ..." ([readings](../../readings/overlay-email-flows.md#a-message-holding-an-injection-and-two-links)).
`overlay/turnState.ts` appends every `thinking` status's detail to `thoughts` as it comes, and the
brain sends each round's reasoning as fresh deltas with nothing between rounds.

## What to do

Put a paragraph break between rounds, either brain side where the tool loop starts a round, or in
`turnState.ts` when a thinking delta follows another status since the last one. The brain side
keeps the overlay thin; check that the thinking filter's held tail is released before the break.

## History

- 2026-10-10: filed from the email flows on the Linux shell.
