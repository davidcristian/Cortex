# The shipped sentence hands the report back on a summarization

**Status:** done 2026-09-13
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

The five-pick re-table of 2026-09-11 drew the five subagent picks on the current image and read them
under the corrected rules, which count the report body handed back as a fault. On the summarization
shape the `constrained` variant, which is the shipped path and includes `REPLY_INSTRUCTION`, hands
the body back far more often than either control:

| pick | raw | bare, the envelope alone | constrained, the envelope and the sentence |
| --- | --- | --- | --- |
| gemma-4-E4B (the default) | 0 of 32 | 2 of 32 | 14 of 32, 12 of them identical to the body in letters and digits |
| Qwen3.5-2B (the roster alternate) | 0 of 32 | 7 of 32 | 27 of 32, 17 of them identical |
| gemma-4-E2B | 0 of 32 | 4 of 32 | 31 of 32 |

Every one of those replies comes back `ok=True`, and the rule the old table was read under counted
each as delivered, since a copy contains every number its body states. So the reply-sentence
change's headline, that the sentence takes the default pick's narrating summarization from 9 of 32
to 29 of 32, reads 11 to 15 on this image under the corrected rules, and on the E2B the sentence
takes that shape from 27 of 32 to none. The extraction and lookup shapes show no such effect.

Whether the rows of 2026-08-28 had the same copies cannot be read, because those samples were not
kept. The harness's summarization instruction asks to keep every detail, which invites a long reply,
and the `bare` variant, which has the same instruction without the sentence, copies far less, so the
sentence is what moves the rate on this wording.

**What closed it.** A reworded sentence, measured against the shipped one on seeded samples. It
keeps both halves of the shipped sentence and names the copy in each: "Your entire response must be
the answer itself, not the text you were given. Do not describe the task, plan an approach, announce
what you are about to write, or repeat the input back." It delivers 117 of 128 against the shipped
wording's 102 on the default pick and 97 against 87 on the roster alternate, over four subtask
shapes, so it ships as `REPLY_INSTRUCTION`. The fourth shape, a summarization asking for the
report's figures rather than every detail, is declared beside the other three in
`scripts/envelopejudges.py`, whose `declared` matches a reply to a shape by the shape's own opening
and returns nothing for a wording it does not have.

**What it bears on.** The decision that the shipped path pays no second completion rests on the
default pick showing 0 of 6 quiet failures. On this image under the corrected rules the default
pick's constrained variant has 19 non-deliveries in 96, and 14 of them, every copy, come back
`ok=True`. [R-480](480-a-narrated-reply-arrives-as-an-answer.md) holds that decision, and the two
differ in kind: that entry's plans and narrations still read 0 on the default pick, while a copy is
a comparison of the reply with the context the runner already has, which needs no second completion.
A runner-side copy refusal is the other fix open here, and it would have to answer the exemption the
rule change names, a subtask that asks for the body back.

## History

- 2026-09-11: opened by the five-pick re-table of 2026-09-11 at the origin, whose seeded samples are
  under `measurements/envelope-retable-2026-09-11/` (git ignores it, one directory per pick).
- 2026-09-11: the close of [R-480](480-a-narrated-reply-arrives-as-an-answer.md) measured a second
  completion on the same tier as the other candidate detector, and it does not reach the copy: asked
  whether the reply it wrote answered, the roster alternate passed 18 of its 27 copies as answers
  while calling 40 of its 59 delivered answers non-answers, and the default passed 5 of its 14
  copies while calling 16 of 77 answers non-answers
  ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) decision 9). So a wording and a
  runner-side comparison with the context are the only fixes left for the copy.
-   2026-09-13: every claim above was checked against the samples the re-table kept, by the judge
   module itself: the three copy tables reproduce reply for reply, and every copy of all three picks
   comes back `ok=True`, which the origin stated of the default pick alone. The candidate wording
   was then drawn on the default pick over the three shapes, on the re-table's image and argv, and
   removed the copy while gaining 14 replies of 96: 91 of 96 against the shipped sentence's 77 and
   the envelope alone's 71, its summarization going from 15 of 32 to 28 with all 14 copies gone, and
   the two variants cut at the cap five times each ([reply
   envelope](../../readings/reply-envelope.md), samples under
   `measurements/envelope-sentence-2026-09-13/`, which git ignores).
- 2026-09-13: the roster alternate and the fourth shape were drawn and the sentence changed
  ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) decision 5). Two of this entry's
  claims narrow with it. The copy is partly the harness's own wording: on a summarization asking for
  the figures rather than every detail the shipped sentence hands the body back 3 times in 32 on the
  default pick and twice on the alternate, against 14 and 27 on the wording this entry was opened
  over. And on the roster alternate no sentence beats no sentence, the envelope alone reading 70 of
  96 against the candidate's 66, which is the disagreement across picks that a per-entry wording was
  declined over. The runner-side copy refusal was not built, since the wording removes the default
  pick's copy.
