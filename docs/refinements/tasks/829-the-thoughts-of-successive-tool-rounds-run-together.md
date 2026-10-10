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

Put a paragraph break between rounds, either brain side in `stream_turn_events`
(`turn_output.py`) when reasoning follows a `ToolStep`, or in `turnState.ts` when a thinking delta
follows another status. Either way the break meets ADR-0015 decision 4: the thinking filter reads
the rounds as one stream, so a URL split across two rounds is redacted whole, which
`test_url_split_across_thinking_bursts_around_a_tool_call_is_redacted` in `test_engine.py` asserts.
A break fed through the filter ends that URL at the round, and a break added after it shows the two
halves apart, so decide which reading the ADR keeps before building either.

## History

- 2026-10-10: filed from the email flows on the Linux shell.
