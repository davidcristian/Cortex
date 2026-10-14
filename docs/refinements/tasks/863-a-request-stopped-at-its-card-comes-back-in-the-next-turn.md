# A request stopped at its card comes back in the next turn

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 1
**Verified:** 2026-10-15

A turn ended by Stop, by a new chat or by any other cancel stores its question and no reply, and
none of its runs, so the next turn's model reads a request nobody answered. An action stopped at
its card can be taken up again, and a stopped essay was taken up in none of 5 rows. On the
Linux shell, Stop at an `escalate_to_brain` card wrote a `DECLINED` audit line, and the next
question in that chat, "What colour is a ripe lemon? One word.", brought back the same card with
the stopped request's brief. A new chat at that card and a third question did the same, and once
approved the cortex answered all three questions in one reply
([readings](../../readings/overlay-interruption-flows.md#stop-or-a-new-chat-while-a-card-waits)).
The person declined the action twice and saw it asked for again.

## Reproduce

On the GPU stack with escalation on, send the `just rpc-handoff` prompt from the overlay, press
Stop while its card waits, then send any short question in the same chat: the card comes back.

## What to do

A candidate that changes no stored data: where `replay_runs` in `cortex_core/tool_replay.py` builds
the model's messages from the history, a stored user message with no reply after it is followed by
a short assistant line saying that turn ended before its reply. That text
is a fixed constant the tests assert, and the overlay shows nothing new. Run the rows and the rule
in [the readings](../../readings/overlay-interruption-flows.md#rows-for-the-stopped-request)
before and after; the candidate ships only on a pass. A stored stopped record is the in-chat pick
of [R-816](816-a-stopped-reply-goes-on-writing-and-is-not-kept.md) and stays with it.

## History

- 2026-10-15: filed from the interruption flows on the Linux shell, with the rows and the pass
  rule written before any baseline.
- 2026-10-15: drew the first baseline: 1 of 5 K rows failed, 2 passed and 2 had not settled
  when read, and 0 of 5 T rows failed, so a stopped text request is not taken up and the rule's
  3 of 5 was not reached. Next: the K rows that wait for turn 2 to settle, written in the readings.
