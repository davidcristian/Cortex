# A deep reply can hold a literal think tag and its text twice

**Status:** done 2026-11-23
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

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
| 2026-11-21, build b12375, 16384, `q8_0`, draft layer, `reasoning_effort` `medium` | 0 | 0 |

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
- 2026-11-21: counted in the rows drawn at `reasoning_effort` `medium` on the drafted launch of
  the same date ([readings](../../readings/deep-effort.md)): 0 of 100 control replies and 0 of
  100 framed replies have the tag, and none of the 5 stop draws. Against the 11 control replies
  at `xhigh` on the same argv that reads p 0.0007, a comparison not written down before the
  draw, and the prediction of 10 (4 to 18) missed. The sentence the template writes at `xhigh`
  and leaves out at `medium` is the one setting between the two rows.
- 2026-11-22: counted on the pick's NVFP4 file, drawn as the model host starts the tier
  ([readings](../../readings/nvfp4-deep-counts.md)): at `reasoning_effort` `medium` with the
  draft layer 0 of 100 control replies and 0 of 100 framed replies have the tag, the Q4 file's
  counts at that level. None of its 36 stop draws has one, 24 at `medium` and 12 at `xhigh`, and
  the reply of its one handoff has none. Its injection rows at `xhigh`, where the Q4 file has
  the tag in 11 and 13 of 100 control replies, are not drawn.
- 2026-11-23: closed on [the think tag readings](../../readings/deep-think-tag.md), each rule
  written before its launch. Only an operator's `high` or empty `CORTEX_REASONING_EFFORT_BRAIN`
  reaches `xhigh`. At the shipped argv, no drafter and `medium`, 0 of 200 more framed replies have
  the tag, 0 of 300 with the row of 2026-11-21, so no check is built for the default. The control
  at `xhigh` reads 14 of 100 at the 16-bit cache and 13 of 100 at 8192 against 13 at `q8_0` and
  16384, so neither setting reads apart, and the 8192 launch reproduced the earlier row draw for
  draw. What is left is the engine build or chance in the row of 2026-09-26; no CUDA engine image
  on b10680 is present, so the build is not drawn. Keeping the text after the last marker
  cannot run on a reply that has already streamed; the check for the operator's `high` is
  [R-1305](1305-a-deep-reply-at-the-high-effort-can-hold-a-think-tag-and-its-text-twice.md).
