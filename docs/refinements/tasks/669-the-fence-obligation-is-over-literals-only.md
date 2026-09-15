# The fence obligation is over literals only

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-15
**Trigger:** a module under `scripts/` decides whether a line is a fence by testing it against
`markdownfences.MARKERS`, or against anything read off that tuple, rather than by asking `Fences`.
One search over the modules importing that name answers it.

Opened 2026-09-15 by the close of
[R-644](644-the-fence-obligation-stops-at-the-suites.md), whose reading of that obligation turned
up the gap while arguing about a different one.

`markdownfences.spelled` walks a module's syntax and returns every line where a string literal
carries a marker. That reports a **copy of the spelling**, which is what it was written for: the
three gates each held the same pattern before the shared answer existed. It reports nothing about
a module that imports `MARKERS` or `CHARACTERS` and builds a second reading out of them, because
such a module writes no marker of its own. The obligation therefore holds the spelling in one
place and says nothing about the reading being in one place, and the second is what the closing
rule made worth holding: a module testing a line against a marker has no opening run to compare
against, so it is back to the toggle the shared answer stopped using.

**Why it was left.** Nothing in this tree does it. The four modules that read markdown take their
answer from `Fences`, and the one that deliberately does not, `rosternames.py`, reads no fence at
all and says in its docstring why. Writing the rule now means deciding what counts as a reading
built on the shared names, which is the same question
[R-644](644-the-fence-obligation-stops-at-the-suites.md) declined to answer by shape for the
suites, and answering it for the modules first would leave the two halves of one rule written in
different shapes.

**What would close it.** Report a module that imports a name from `markdownfences` other than
`Fences` and `spelled`, which is a rule over imports rather than over positions and so avoids the
enumeration that sank the shape rule. `MARKERS` would then be private to the module that answers
for it, and a gate needing the characters would have to ask for an answer rather than for the
alphabet. The alternative is to say at the origin that the obligation is over the spelling on
purpose, with the reading held by the fact that there is one module to import from.
