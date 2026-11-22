# The gemma NVFP4 file has none of the rows the deep pick is compared on

**Status:** declined 2026-11-22
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

ADR-0004 decision 8 picks the deep tier's model on fit inside the model budget, with the other
axes level. The rows behind those axes are the stop row (four written questions, three
seeds each, counted as stopped and as right by hand), the reasoning tokens a draw spends, and the
framed and unframed injection draws. They were drawn on `gemma-4-31B-it-qat` and
`Qwen3.8-27B-UD-Q4_K_M` and are in [deep candidates](../../readings/deep-candidates.md).

The models mount holds an NVFP4 file of each model, with memory and rate rows in
[the NVFP4 files for the deep tier](../../readings/nvfp4-deep-tier.md). NVFP4 is another 4-bit
encoding of the same weights, so a count drawn on a Q4 file is not a count for the NVFP4 file of
that model.

- **The Qwen NVFP4 file has its rows.** They were drawn on 2026-11-22 as the model host starts
  the tier, beside the Q4 file's rows of 2026-11-21 on the same engine build, and are in
  [what the Qwen NVFP4 file writes](../../readings/nvfp4-deep-counts.md). No count reads apart
  from the Q4 file's by the marks in the Prediction below.
- **The gemma NVFP4 file has none.** Its rate rows show one difference already: at draft length 1
  the engine accepts 0.59 of the drafter's tokens beside the NVFP4 file against 0.81 beside the
  Q4 file on 2026-11-22, so the NVFP4 file's next token differs from the drafter's more often.

What is not known:

- Whether the gemma NVFP4 file stops on as many of the twelve stop-row draws as its Q4 file, and
  how many reasoning tokens a draw spends.
- Whether it obeys a framed or an unframed injection draw more often than its Q4 file.

Why it waited: the rows were wanted only if the choice of
[R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md) named the
gemma NVFP4 file, and on 2026-11-22 that choice kept both Q4 files. The NVFP4 file does not
fit whole on the 24 GB card. Split with RAM on 2026-11-22 it wrote 0.85 of its Q4 file's rate
without drafting and 0.67 with the drafter, so its rows would cost more card time than the
Qwen file's did.

What would close it: the stop row and the injection row drawn on the gemma NVFP4 file as the
stack would start it, on the engine build the model host runs, with the gemma Q4 file drawn the
same way on that build beside it and the count that reads apart written first. The drivers are
`stop16.py` and `inj16m.py` in `~/.cache/cortex-run/2026-11-22/v1/`. The rows go into a readings
record beside the Qwen file's. A choice in R-1244 that does not name the file closes it as
declined.

## Prediction

Written on 2026-11-22 before the first counted draw on the Qwen NVFP4 file, for the rows the Q4
file has from 2026-11-21: the tier as the model host starts it at 16384, one slot, `q8_0`, build
b12375.

| row | Q4 file | NVFP4 file, predicted (range) | reads apart at |
| --- | --- | --- | --- |
| stops, draft layer, `medium` | 12 of 12 | 12 (11 to 12) | 7 or fewer |
| stops, no drafter, `medium` | 12 of 12 | 12 (11 to 12) | 7 or fewer |
| stops, draft layer, `xhigh` (nothing sent) | 12 of 12 | 12 (11 to 12) | 7 or fewer |
| stops, no drafter, `xhigh` (nothing sent) | 11 of 12 | 11 (9 to 12) | 5 or fewer |
| right by hand, draft layer, `medium` | 12 of 12 | 11 (10 to 12) | 7 or fewer |
| right by hand, no drafter, `medium` | 11 of 12 | 11 (10 to 12) | 5 or fewer |
| right by hand, draft layer, `xhigh` | 11 of 12 | 11 (9 to 12) | 5 or fewer |
| median reasoning tokens, draft layer, `medium` | 2378 | 2000 (1100 to 3300) | under 951 or over 5945 |
| median reasoning tokens, no drafter, `medium` | 1182.5 | 1700 (1000 to 3000) | under 473 or over 2956 |
| median reasoning tokens, draft layer, `xhigh` | 2883.5 | 2700 (1500 to 4500) | under 1153 or over 7209 |
| framed injection draws obeyed or void, `medium` | 0 of 100 | 0 (0 to 3) | 6 or more |
| unframed injection draws obeyed or void, `medium` | 0 of 100 | 0 (0 to 4) | 6 or more |
| a literal `</think>` in a reply, each injection row | 0 of 100 | 0 (0 to 3) | 6 or more |

- **The marks.** A count reads apart by the two-sided Fisher test at p below 0.05, the test the
  Q4 file's rows used. The mark for a median is a factor of 2.5 either way. The Q4 file's two
  `medium` cells differ only in the drafter and read 2378 and 1182.5, a factor of 2.01, so a
  smaller factor is inside what one file shows between two cells.
- **The handoff.** Predicted: every pass item of the Q4 file's handoff holds, the brain logs one
  `reasoning effort sent` line with `sent_as=medium`, the card's highest reading is 16,700 MiB
  above the floor (16,600 to 16,800) against 16,995 for the Q4 file, the load is 0.19 of its
  bound (0.15 to 0.25) and the first token 0.02 of its bound (0.01 to 0.03).
- **The result predicted:** no row reads apart from the Q4 file's.

A row the time box does not reach is named as not drawn.

## History

- 2026-11-18: filed when R-1244 drew the memory and rate rows of the two files and found that the
  rows the pick rests on do not exist for either.
- 2026-11-20: the Q4 file of Qwen3.8-27B is drawn on build b12375 at the shipped 16384 by
  [R-1266](1266-qwen38-27b-has-no-stop-row-at-the-shipped-16384-context.md) and
  [R-1267](1267-qwen38-27bs-injection-row-was-drawn-at-8192-on-an-earlier-build.md), which are the rows of that
  build this task asks for beside the Qwen NVFP4 file's.
- 2026-11-22: the Qwen NVFP4 file's rows drawn on build b12375 as the model host starts the tier,
  at 16384 and `q8_0` ([readings](../../readings/nvfp4-deep-counts.md)). It stopped on 12 of 12
  at `medium` with its draft layer and without it, and on 11 of 12 at `xhigh` with the layer; at
  `medium` 0 of 100 framed and 0 of 100 control injection draws obeyed; one handoff through the
  brain held every reading the Q4 file's handoffs passed on. No count reads apart from the Q4
  file's by the marks above, and every prediction in the table held for the rows drawn. Two of
  the handoff's missed: the card's highest reading, 3 MiB over its range, and the first token,
  which both files drawn in turn read the same way
  ([readings](../../readings/nvfp4-deep-pair.md#the-deep-turn-of-a-handoff)).
  The undrafted `xhigh` cell and the injection rows at `xhigh` were not drawn.
  What is left here is the gemma NVFP4 file, which the task now names and waits on the choice
  of R-1244 for.
- 2026-11-22: declined. The maintainer's choice in R-1244 keeps the Q4 file for both deep
  entries, so no choice names the gemma NVFP4 file and its rows are not wanted.
