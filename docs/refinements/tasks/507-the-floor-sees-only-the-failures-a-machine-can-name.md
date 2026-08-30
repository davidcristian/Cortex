# The floor sees only the failures a machine can name

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-08-30 by the close of
[R-484](484-the-control-arm-is-held-to-no-floor.md), which put a floor under the control arm and
built it on the half of a failing reply a reader can see without knowing the subtask.

`scripts/envelopefloor.py` counts a run as having **stood** when the runner accepted it, the reply
is not empty, and the reply is not the instruction handed back. Those three are visible whatever
was asked, which is what lets the floor hold a harness whose subtask is a knob
(`CORTEX_ENVELOPE_INSTRUCTION`). What the addenda's tables count instead is **delivered**, judged
by number recall against the body on a summarization and an extraction and by whether the reply
names the body's own reporting period on a lookup, with two arbitrations on top of that: a comma
read once as a thousands separator and once as a separator, and a strict reading that counts a run
cut at the cap as a non-delivery whatever its text held. That judging is still done by hand, in a
scratchpad, once per sweep.

So the two numbers are not the same number, and the gap is exactly the failure mode this arc is
about. A reply that narrates the subtask rather than doing it is well formed, accepted, non-empty
and not an echo, and it **stands**. On the shipped constrained path of the default pick, 23 of 24
bare non-deliveries were `ok=True` narrations of precisely that kind. A lookup answered `Fortnite
18` stands too. The floor is therefore sound in the direction that matters, `stood` bounding
`delivered` from above so a refusal is always honest, and blind in the other: a control arm could
narrate every one of its 96 runs and clear the floor.

**It was demonstrated on real replies the day the floor landed**, and by accident. A four-run probe
of the lookup shape on Qwen3.5-0.8B Q8_0, at a 256-token cap on CPU, published `stood on 4 of 4`
for its control arm. Read the four replies and one of them answers: `Week 34`. The other three say
`week ending Wednesday, July 29, 2024`, `the month of April` and `the second half of the month`,
against bodies whose own periods are `week 34` and `month ending`. So the judged rate of that cell
is 1 of 4 where the machine-read rate is 4 of 4. Four runs at a starved cap is a probe and says
nothing about the pick, which the row already measured at 30 of 32 on this shape; what it shows is
the size of the gap between the two rates, on the shape where the judge is not even a proxy.

**What is wrong with the present shape.** Nothing is wrong with the floor; what is missing is the
other half. Two rates now describe one run, one of them computed by a covered module and one of
them by a person, and only the weaker one is written down anywhere a machine can check. The next
sweep's tables will still be judged by hand, and the hand judging is where the arc's readings
actually come from.

**What would close it.** The judge moving into the reader, which means answering the thing that
kept it out: a judge is a function of the subtask, and the harness deliberately lets the subtask be
anything. The shape worth pricing first is a judge **per shape rather than per run**, declared
beside the instruction it belongs to (a recall proxy for the two number shapes, a period regex for
the lookup) and simply absent for an instruction nobody declared one for, in which case the reader
publishes `stood` alone and says so. That keeps a run with a hand-typed instruction working, gives
the three shapes this arc actually sweeps a machine-checked `delivered`, and would let the floor be
held on the rate the tables really quote. The arbitrations are the part to be careful with: they
are readings and not rules, so a judge that hard-codes the charitable comma or the strict cap
reading has quietly changed what the record's columns mean, and each needs to be a stated column
rather than a default.

Worth deciding at the same time: whether `delivered`, once a machine computes it, should carry its
own floor or stay a printed number. The argument for a floor is that it is the rate the record
quotes; the argument against is that it is the rate under measurement on every arm but one, and an
instrument that reddens on its own subject is not an instrument.

## Trail

- 2026-08-30: opened by the close of
  [R-484](484-the-control-arm-is-held-to-no-floor.md), which built the floor on the failures a
  reader can name without knowing the subtask and left the judging that names the rest by hand.
