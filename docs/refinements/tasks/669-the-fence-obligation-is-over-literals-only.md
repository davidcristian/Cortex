# The fence obligation is over literals only

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)
**Verified:** 2026-09-19
**Trigger:** a module under `scripts/` decides whether a line is a fence by testing it against
`markdownfences.MARKERS`, or against anything read off that tuple, rather than by asking `Fences`.
One search over the modules importing any name from `markdownfences` other than `Fences` and
`spelled` answers it, since `CHARACTERS` and `LEAST` are both read off the tuple.

`markdownfences.spelled` walks a module's syntax and returns every line where a string literal
contains a marker. That reports a second copy of the literal, which is what it was written for: the
three checks each had the same pattern before the shared reader existed. It reports nothing about a
module that imports `MARKERS` or `CHARACTERS` and builds a second reading out of them, because such
a module writes no marker of its own. So the rule keeps the literal in one place and says nothing
about the reading being in one place, and the second is what the closing rule made worth checking: a
module testing a line against a marker has no opening run to compare against, so it is back to the
toggle the shared reader stopped using.

**Why it was left.** Nothing in this tree does it. The four modules that read markdown take their
answer from `Fences`, three by importing it and `backloganchors.py` through the headings
`headingshapes.py` hands it, and the one that deliberately does not, `rosternames.py`, reads no
fence at all and says in its docstring why. Writing the rule now means deciding what counts as a
reading built on the shared names, which is the same question
[R-644](644-the-fence-obligation-stops-at-the-suites.md) declined to answer by shape for the suites,
and answering it for the modules first would leave the two halves of one rule written differently.

**What would close it.** Report a module that imports a name from `markdownfences` other than
`Fences` and `spelled`, which is a rule over imports rather than over positions and so avoids the
enumeration that sank the shape rule. `MARKERS` would then be private to the module that answers for
it, and a check needing the characters would have to ask for an answer rather than for the alphabet.
The alternative is to say at the origin that the rule is over the literal on purpose, with the
reading kept in one place by there being one module to import from.

## History

- 2026-09-15: opened by the close of
  [R-644](644-the-fence-obligation-stops-at-the-suites.md), whose reading of that rule turned up the
  gap while arguing about a different one.
- 2026-09-19: checked again and left open, the trigger unfired. Three modules import from
  `markdownfences`, `commitlint.py`, `headingshapes.py` and `logsamples.py`, and each imports
  `Fences` alone; `backloganchors.py` reads fences only through `headingshapes.headings`, which the
  paragraph above now says rather than counting it as a fourth importer. The one importer of
  `MARKERS` is `tests/test_markdownfences.py`, which parametrizes the suite of the module that owns
  it and decides no fence. The search the trigger named was over importers of `MARKERS` alone and
  would have missed a module reading `CHARACTERS` or `LEAST`, so it now covers every name but the
  two a check is meant to use. A `MARKERS` tuple in `switchtail.py` is a near miss by name only: it
  holds a model's thought markers and has nothing to do with fences. No commit since the one that
  filed this entry has touched `markdownfences.py`, and the one that touched an importer since
  changed no line reading a fence.
