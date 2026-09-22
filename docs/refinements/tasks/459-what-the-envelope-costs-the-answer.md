# Nothing measures what the reply envelope costs the answer rather than the tokens

**Status:** done 2026-08-28
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Everything measured about the reply envelope was a length: decoded tokens, wall clock, characters
returned. Nobody had checked whether the answer is as good. The first readings taken with the
reasoning trace off were not reassuring: over the three report bodies the envelope measurement is
built around, every constrained run finished well inside the cap (63 to 89 decoded tokens, 223 to
395 characters) and all three narrated the task instead of performing it, while the same bodies
unconstrained returned 1512 to 2211 characters of actual summary.

Three runs of a 4B model prove nothing, so what this entry asked for was the same paired
measurement over enough bodies to tell a tendency from a single draw, comparing the replies as
answers rather than as sizes.

## History

- 2026-08-26: opened by the close of
  [R-456](456-a-constrained-request-loses-the-thinking-switch.md), whose live proof left three
  constrained replies that all narrated the task.
- 2026-08-28: closed. Measured through the committed harness on llama.cpp `b10644-d7a207411`, four
  report bodies at ten draws each over four request shapes, 160 runs, judged by number recall (the
  fraction of a body's own numeric literals a reply contains) and by a reader's classification of
  every reply. The measure separates cleanly: not one of the 160 falls between 0.09 and 0.82. The
  envelope does not shorten the answer, it deletes it three times in four. The unconstrained shape
  delivered a summary on 40 of 40 draws and the shipped envelope on 10 of 40 (Wilson 95%, 0.91 to
  1.00 against 0.14 to 0.40); the other thirty narrate. When it answers, it answers as well as the
  unconstrained shape, so the cost is arrival and not quality. Giving `reply` a description changed
  nothing (9 of 40), and could not have: asked through `POST /apply-template`, this pick renders a
  byte-identical prompt with the envelope and without it, so a schema constrains the next token and
  never describes a contract. A second required field ahead of `reply` changed nothing either
  (10 of 40). What does move it is the subtask text: an instruction naming what the reply must
  contain takes the same schema to 39 of 40. Nothing in the shipped tree changed, which is this
  entry's own caution kept. Written into ADR-0028; the harness gained the two schema variants, a
  draw count and an instruction override, so every reading is repeatable. Opened by it:
  [R-476](476-the-envelopes-answer-rate-is-an-instruction.md), which holds the decision this
  measurement declines to make, and
  [R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md), because the firmer instruction
  relocates the plan rather than removing it: three draws in forty put it in the reasoning channel,
  the first seen here on a server started with both reasoning-off flags.
