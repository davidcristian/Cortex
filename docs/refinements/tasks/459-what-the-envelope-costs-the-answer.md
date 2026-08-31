# Nothing prices what the reply envelope costs the answer rather than the tokens

**Status:** landed 2026-08-28
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-26 by the close of
[R-456](456-a-constrained-request-loses-the-thinking-lever.md), whose live proof was the first
sight of the constrained shape answering without a reasoning trace.

Everything measured about the envelope so far is a length: decoded tokens, wall clock, characters
returned. Nobody has read whether the answer is as good. The first readings taken with the trace
off are not reassuring. Over the three report bodies the envelope measurement is built around, at
the shipped cap, every constrained run finished well inside it (63 to 89 decoded tokens, 223 to 395
characters) and **every one of the three narrated the task instead of performing it**: "The user
wants a comprehensive summary of the provided site report", "I need to summarize the provided text
while ensuring every single detail is retained", and one that spends its whole reply arguing the
instruction contradicts itself. The same bodies raw returned 1512 to 2211 characters of actual
summary. Read plainly, this model writes into `reply` what it used to write into
`reasoning_content` now that nothing else will take it.

**Why it was left.** Three draws from a 4B model price nothing, and the entry it comes from was a
defect with a live before and after, not a quality study. Acting here would mean changing the
grammar every delegated reply is decoded into on the strength of three readings, which is the kind
of mistake this backlog exists to prevent.

**What would close it.** The harness already runs both shapes over the same bodies, so the
measurement is a reading rather than a build: run the paired arms at the shipped cap with the tier
fixed and compare the replies as answers, not as sizes, over enough bodies that one thin draw is
visible as one. The honest outcomes are three: the envelope costs nothing and the reading above was
a draw, it costs a little and the niche it defends is still worth it (ADR-0028's argument is
format-laundering on a weak model, not answer quality), or it costs enough that the tool-less shape
wants a different grammar. Worth measuring in the same run: whether the model writes a better answer
when the envelope's `reply` property carries a description, since an empty schema tells it nothing
about what the field is for.

## Trail

- 2026-08-26: opened by the close of
  [R-456](456-a-constrained-request-loses-the-thinking-lever.md), whose live proof left three
  constrained replies that all narrated the task and nothing that could say whether three was a
  reading or a draw.
- 2026-08-28: Landed, on the third of the three outcomes it named, with a correction to that
  outcome's wording. Measured through the committed harness on llama.cpp `b10644-d7a207411`, four
  report bodies at ten draws each over four request shapes, **160 runs**, judged by number recall
  (the fraction of a body's own numeric literals a reply carries) and by a reader's classification
  of every reply. The proxy separates rather than ranks: not one of the 160 lands between 0.09 and
  0.82.
  **The envelope does not shorten the answer, it deletes it three times in four.** The
  unconstrained shape delivered a summary on **40 of 40** draws and the shipped envelope on **10 of
  40** (Wilson 95%, 0.91 to 1.00 against 0.14 to 0.40); the other thirty narrate. When it answers it
  answers as well as raw, so the cost is arrival and not quality.
  **The arm this entry asked for is answered and the answer is a mechanism.** Giving `reply` a
  description changed nothing (9 of 40), and it could not have: asked through `POST /apply-template`
  with both controls firing, this pick renders a byte-identical prompt with the envelope and
  without it, so a schema constrains the next token and never describes a contract. A second
  required field ahead of `reply`, added as a fourth arm so the narration had somewhere else to go,
  changed nothing either (10 of 40); the model narrates into both. What does move it is the subtask
  text, the one channel that reaches the model: an instruction naming what the reply must contain
  takes the same grammar to **39 of 40**.
  So the outcome is that the tool-less shape costs enough to want a repair, and the repair is not a
  grammar. Nothing in the shipped tree moves here, which is this entry's own caution kept. Written
  into the ADR-0005 answer addendum, with the envelope's own argument re-read in the ADR-0028
  answer-rate addendum. The harness gained the two schema arms, a draw count and an instruction
  override, so every reading above is re-runnable.
  Opened by it: [R-476](476-the-envelopes-answer-rate-is-an-instruction.md), which carries the
  decision this measurement declines to type, and
  [R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md), which carries the residue found
  under it: the firmer instruction does not remove the plan, it relocates it, and the three draws in
  forty where it went to the reasoning channel are the first in this repo on a server carrying both
  reasoning-off flags.
