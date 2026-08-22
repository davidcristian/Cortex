# A second spelling of a value shares a line the registry already holds, and rides its needle

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-382](382-the-paired-numbers-quoted-in-prose.md), which sorted the legibility pair's prose and
found a shape the sort has no clean answer for.

`docs/runbooks/vision.md` line 53 spells `2048` twice: once in the table's Default cell, which the
registry pins by the whole of that row, and once in the sentence after it, which calls that number
the brain half of the pair that makes a 4K screen legible. Both state the shipped edge and both
become wrong when it moves. Only the first is held, and because a
mention is a presence check the second could drift to any number with the gate green, leaving one
line naming two different shipped edges.

The same shape closed on the neighbouring value rather than opening here, because that one had a
structural needle available: the GPU runbook's Example cell holds nothing but the number, and cell
walls pin a value without pinning a word of the sentence. The vision runbook's second spelling has
no such walls. Every needle that reaches it has to carry four words of an explanation, which is
exactly what the survey's own rule forbids: a gate reddening because somebody reworded a sentence
that never moved.

**Why it was left.** The three ways out are each a decision rather than a row. Counting the line's
occurrences ties the Default cell and the sentence into one set, which is true here and would be
false the moment a third spelling arrives for a different reason. Rewriting the sentence to reach
the value through a shape the registry already pins is the gate editing the prose it watches.
Teaching a mention to pin a value's occurrences **within one line** is a change to `couplings.py`
and to the scan, and is the only one of the three that generalises.

**What would close it.** Decide which of the three the repo wants, and say why in the ADR rather
than in a row. Read the population first: this entry names one line, and a scan for a registered
value appearing twice on a line whose first spelling is held would say whether it is one line or
twenty. If it is one, a count is honest and cheap; if it is many, the scan change earns itself.

## Trail

- 2026-08-23: opened by the close of
  [R-382](382-the-paired-numbers-quoted-in-prose.md), which held both cells of the GPU runbook's
  row and could not hold the vision runbook's second spelling by any needle that pins the number
  rather than the sentence.
