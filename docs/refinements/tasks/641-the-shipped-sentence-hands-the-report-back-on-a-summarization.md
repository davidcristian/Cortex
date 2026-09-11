# The shipped sentence hands the report back on a summarization

**Status:** open, actionable
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
