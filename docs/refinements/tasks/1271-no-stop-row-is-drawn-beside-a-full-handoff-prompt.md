# No stop row is drawn beside a full handoff prompt

**Status:** done 2026-11-23
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Every stop row sends the plain security preamble and one question, a prompt of about 300 tokens,
so a draw has nearly the whole context to reason in
([the stop rows at 16384](../../readings/deep-candidates.md#the-stop-rows-at-16384)). A handoff
sends the chat with the question. A full 24,000 character window with the deep tier's tools
leaves 5,521 to 6,873 tokens of the 16384
([history window](../../readings/history-window.md#the-cortexs-whole-prompt)).

On 2026-11-21, at the template's own `xhigh`, 5 of the 24 draws of Qwen3.8-27B generated
more than 5,521 tokens: 6,799, 6,960, 11,169, 15,610 and 16,080. Four of the five count as
stopped in the 16384 rows. So does the one `medium` draw of 24 that did, at 10,207 without a
drafter, and the one `low` draw of 12, at 7,086 with the draft layer.

## What to draw

The four questions, three seeds each, behind a prompt filled to about 10,800 tokens, on the deep
pick as the model host starts it: at the default `medium` and at `xhigh`, and the same row on
gemma-4-31B. Count the draws that stop with a reply.

What would close it: the row in deep candidates, and ADR-0004 decision 8 stating the stop count
for the room a handoff leaves. Declined if
[R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md) ships an
effort at which no draw of the 16384 rows generates more than 5,521 tokens.

## History

- 2026-11-21: filed by the stop rows at 16384
  ([R-1266](1266-qwen38-27b-has-no-stop-row-at-the-shipped-16384-context.md)).
- 2026-11-21: `medium` is the deep tier's default effort since
  [R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md) closed, and
  the decline condition is not met. Of the 24 `medium` draws at 16384, the 12 drafted ones
  generated at most 5,123 tokens and one undrafted draw generated 10,207
  ([readings](../../readings/deep-effort.md#the-drafted-medium-stop-cell)). The row is still to
  draw.
- 2026-11-23: drawn behind a prompt of 10,800 tokens on engine build b12375, each entry started
  by the model host with its file named, with the pass rule written before the first launch
  ([readings](../../readings/deep-handoff-room.md)). The pick with its draft layer stopped with a
  reply on 11 of 12 at `medium` and 11 at `xhigh`, and the alternate's `UD-Q4_K_XL` file on 9.
  ADR-0004 decision 8 now gives those counts. The rule files nothing at 11, and filed
  [R-1302](1302-a-full-handoff-prompt-leaves-the-alternate-deep-model-too-little-context-to-reply.md)
  for the alternate's 9.
