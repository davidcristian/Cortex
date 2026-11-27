# A deep reply at the high effort can hold a think tag and its text twice

**Status:** open, waiting for its trigger
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Trigger:** the default of CORTEX_REASONING_EFFORT_BRAIN leaves medium, or a framed row at medium has a reply with the tag.
**Verified:** 2026-11-27

At the `high` level, which the brain sends as `xhigh`, and with no level sent, which the Qwen3.8
template renders as its own `xhigh`, the deep pick sometimes writes its reply, a line holding only
`</think>`, and the reply again, all in `content`. The brain shows and stores that reply as it
came. Only an operator's setting of `CORTEX_REASONING_EFFORT_BRAIN` reaches either level; at the
default `medium` none of 300 framed replies has the tag
([readings](../../readings/deep-think-tag.md)).

| request at `xhigh` on build b12375 | replies with the tag |
| --- | --- |
| framed: the brain's preamble, framing, tools and one tool result | 1 of 200 |
| control: no system message, the tool result unframed, a request the brain never sends | 38 of 300 |

Keeping the text after the last marker cannot run on what the brain shows: the reply streams as
`TextDelta` events (`stream_turn_events` in `cortex_core/turn_output.py`), and
`proto/body.proto` has no event that takes shown text back, so the first copy is on the screen
before the marker arrives. Two forms remain:

- **End the completion's shown text at the marker line.** The first line of a completion's text
  that holds only the closing marker, with no opening marker before it and text before it, ends
  what is shown and stored of that completion; with nothing before it, only the line is dropped.
  Replayed over all 1306 recorded deep replies, it ends each of the 52 tagged replies at a whole
  first copy and changes none of the others
  ([readings](../../readings/deep-think-tag.md#the-stream-consistent-form-replayed)). It withholds
  the answer in a form no recorded reply has: thinking before the marker and the answer after it.
  It filters text only, so a tool call after the line still runs; the one tagged reply with a
  call wrote a sentence of reasoning after the line and called the `send_email` the file asked
  for.
- **A body event that replaces the shown reply**, so the text after the last marker is kept. This
  changes `proto/body.proto`, the overlay and the Tauri shell.

Either form needs the tier's closing marker, which `/props` does not name on build b12375.

**What closes it.** One form built, with near-miss tests written first (the marker quoted inside a
line, an opening marker before it, the person's message holding it, the marker split across two
deltas) and replayed over the recorded replies; or a decline that states the rate at `high`.

## History

- 2026-11-23: filed by
  [R-1273](1273-a-deep-reply-can-hold-a-literal-think-tag-and-its-text-twice.md), which closed on
  the rate at the default level.
- 2026-11-27: checked again and not fired: `CORTEX_REASONING_EFFORT_BRAIN` still defaults to
  `medium` in `config_swap.py`, and no deep reply in the readings committed since 2026-11-23 holds a
  literal `</think>`.
