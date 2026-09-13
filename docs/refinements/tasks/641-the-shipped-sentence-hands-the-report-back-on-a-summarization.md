# The shipped sentence hands the report back on a summarization

**Status:** landed 2026-09-13
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-09-11 by the close of
[R-640](640-the-five-pick-envelope-table-is-on-an-image-the-stack-no-longer-pulls.md). The
re-table addendum at the origin drew the five subagent picks on the current image and read them
under the corrected rules, which count the report body handed back as a lapse. On the summarization
shape the `constrained` arm, which is the shipped path and carries `REPLY_INSTRUCTION`, hands the
body back far more often than either control:

| pick | raw | bare, the envelope alone | constrained, the envelope and the sentence |
| --- | --- | --- | --- |
| gemma-4-E4B (the default) | 0 of 32 | 2 of 32 | 14 of 32, 12 of them identical to the body in letters and digits |
| Qwen3.5-2B (the roster alternate) | 0 of 32 | 7 of 32 | 27 of 32, 17 of them identical |
| gemma-4-E2B | 0 of 32 | 4 of 32 | 31 of 32 |

Every one of those runs comes back `ok=True`, and the rule the old table was read under counted each
as delivered, since a copy carries every number its body states. So the instruction addendum's
headline, that the sentence recovers the default pick's narrating summarization from 9 of 32 to 29
of 32, reads 11 to 15 on this image under the corrected rules, and on the E2B the sentence takes
that shape from 27 of 32 to none. The extraction and lookup shapes show no such effect.

**What is not known.** Whether the rows of 2026-08-28 carried the same copies cannot be read,
because those samples were not kept. The harness's summarization instruction asks to keep every
detail, which invites a long reply, and a cortex phrasing its own summarization may draw fewer
copies; the `bare` arm, which carries the same instruction without the sentence, copies far less,
so the sentence is what moves the rate on this wording.

**What would close it.** A decision on the sentence, made on seeded samples: a wording that tells
the tier an answer is not the input handed back, measured against the current one on the three
shapes of the harness and on a summarization worded without "every detail", on the default pick and
the roster alternate at least. The per-entry wording addendum at the origin kept one wording for
every entry, and nothing here changes that choice by itself.

**One such wording has now answered on the default pick**, in the candidate-sentence addendum at the
origin, which is the first half of that measurement and not a decision. It keeps both halves of the
shipped sentence and names the copy in each: "Your entire response must be the answer itself, not
the text you were given. Do not describe the task, plan an approach, announce what you are about to
write, or repeat the input back." Over the three shapes at four bodies and eight draws it delivers
91 of 96 against the shipped sentence's 77 and the envelope alone's 71, its summarization goes from
15 of 32 to 28 with all 14 copies gone, and the two arms are cut at the cap five times each. What is
left to measure before the sentence can be changed is the roster alternate, whose constrained
summarization hands the body back 27 times in 32, and the summarization worded without "every
detail". Reading that fourth shape needs a judge declared for it in `scripts/envelopejudges.py`,
whose `declared` matches a run to a shape on the shape's own opening and returns nothing for a
wording it does not carry, so the shape cannot be read until it is named there.

**Both were then measured and the sentence changed**, in the sentence-change addendum at the
origin. The candidate ships as `REPLY_INSTRUCTION`, and the fourth shape, a summarization asking
for the report's figures rather than every detail, is declared beside the other three in
`scripts/envelopejudges.py`.

**What it bears on.** The decision that the shipped path pays no second completion rests on the
default pick showing 0 of 6 quiet failures. On this image under the corrected rules the default
pick's constrained arm has 19 non-deliveries in 96, and 14 of them, every copy, come back `ok=True`.
[R-480](480-a-narrated-reply-arrives-as-an-answer.md) is the entry holding that decision, and
where the two disagree is the kind: that entry's plans and narrations still read 0 on the default
pick, while a copy is a comparison of the reply with the context the runner already holds, which
needs no second completion. A runner-side copy refusal is the other remedy open here, and it has to
answer the exemption the lapse addendum names, a subtask that asks for the body back.

## Trail

- 2026-09-11: opened by the re-table addendum at the origin, whose seeded samples are under
  `measurements/envelope-retable-2026-09-11/` (ignored, one directory per pick).
- 2026-09-11: the close of [R-480](480-a-narrated-reply-arrives-as-an-answer.md) measured a second
  completion on the same tier as the other candidate detector, and it does not reach the copy: asked
  whether the reply it wrote answered, the roster alternate passed 18 of its 27 copies as answers
  while calling 40 of its 59 delivered answers non-answers, and the default passed 5 of its 14
  copies while calling 16 of 77 answers non-answers
  ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) self-judge addendum). So the two
  remedies this entry names, a wording and a runner-side comparison with the context, are the only
  ones left for the copy.
- 2026-09-13: every claim above re-derived from the samples the re-table run kept, by the judge
  module itself: the three copy tables reproduce run for run, and every copy of all three picks
  comes back `ok=True`, which the origin stated of the default pick alone. The candidate wording in
  the section above was then drawn on the default pick over the three shapes, on the re-table
  addendum's image and argv, and removed the copy while gaining 14 runs of 96
  ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) candidate-sentence addendum,
  samples under `measurements/envelope-sentence-2026-09-13/`, which git ignores). The entry stays
  open: one pick is the evidence shape that shipped the sentence this entry is about.
- 2026-09-13: the roster alternate and the fourth shape were drawn, which is what this entry was
  waiting for, and the sentence changed
  ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) sentence-change addendum). The
  candidate delivers 117 of 128 against the shipped wording's 102 on the default pick and 97 against
  87 on the roster alternate, over four subtask shapes, so it ships. Two of this entry's claims
  narrow with it. The copy is partly the harness's own wording: on a summarization asking for the
  figures rather than every detail the shipped sentence hands the body back 3 times in 32 on the
  default pick and twice on the alternate, against 14 and 27 on the wording this entry was opened
  over. And on the roster alternate no sentence beats no sentence, the envelope alone reading 70 of
  96 against the candidate's 66, which is the lineup disagreement the per-entry wording was declined
  over rather than anything this wording can answer. The runner-side copy refusal this entry names
  as the other remedy was not taken: the wording removes the default pick's copy, and the samples
  are under `measurements/envelope-sentence-2026-09-13/`, which git ignores.
