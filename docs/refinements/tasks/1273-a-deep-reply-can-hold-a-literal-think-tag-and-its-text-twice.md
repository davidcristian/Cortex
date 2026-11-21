# A deep reply can hold a literal think tag and its text twice

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-21

Qwen3.8-27B, the deep pick, sometimes closes its thought, writes its reply, writes `</think>` a
second time and writes the reply again. The engine splits the reasoning from the reply at the
first `</think>`, so the second one and both copies of the reply arrive as `content`:

```text
The Q3 planning notes record a 12% quarter-over-quarter revenue increase and a plan to hire two
engineers in October.
</think>

The Q3 planning notes record a 12% quarter-over-quarter revenue increase and a plan to hire two
engineers in October.
```

Counted over the [injection text rows](../../readings/injection-text-rows.md) by a search for the
literal `</think>` in `content`:

| row | framed, of 100 | control, of 100 |
| --- | --- | --- |
| 2026-09-26, build b10680, 8192, 16-bit cache, no drafter | 0 | 2 |
| 2026-11-21, build b12375, 16384, `q8_0`, draft layer | 0 | 11 |
| 2026-11-21, build b12375, 16384, `q8_0`, no drafter | 1 | 13 |

- The control sends no system message and the tool result unframed, a request the brain does not
  send. The framed variant sends the brain's preamble and framing, and read 1 of 200 on
  2026-11-21: a `refusal-suppression` draw, the summary on both sides of the tag.
- None of the 55 stop-row draws of 2026-11-21, which send the preamble and no tools, has one.
- The draft layer does not move the count: 11 against 13, p 0.83.
- The control count rose against 2026-09-26, p 0.018 and 0.0055. The build, the context and the
  cache type all changed between the two dates, so the rise is assigned to none of them.
- One undrafted control draw of 2026-11-21 called `read_file` a second time and ended its text
  with a stray `</parameter>` and `</invoke>`.

The brain reads `reasoning_content` and `content` as the engine splits them
(`cortex_inference/decode.py`), and no code reads a `</think>` inside `content`. A reply like the
one above would be shown and stored with the tag and both copies.

## What to do

- Separate the rise first: the control row on build b12375 at the 16-bit cache and at 8192, one
  setting changed per launch, 100 draws each.
- Draw the framed count deeper. 1 of 200 does not say how often a handoff's reply has the tag: a
  row of requests shaped as a handoff sends them, with the preamble, the tools and a tool result.
- If the tag recurs there, a typed check of the reply in the brain: when `content` has the closing
  marker of the tier's thought pair, keep the text after the last one. The safe direction is to
  show the reply as it came when nothing follows the marker.

What would close it: the rise assigned to one setting or to chance, the framed rate on the deeper
row, and either the check, replayed over the 25 replies recorded on 2026-11-21, or a decline that
states the rate.

## History

- 2026-11-21: filed by the injection rows at the shipped configuration
  ([R-1267](1267-qwen38-27bs-injection-row-was-drawn-at-8192-on-an-earlier-build.md)).
