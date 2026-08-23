# A second spelling of a value shares a line the registry already holds, and rides its needle

**Status:** landed 2026-08-23
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
- 2026-08-23: landed as four ordinary mentions and **no new mechanism**, the population having
  decided it. Eleven held lines carry a leftover spelling; six are artefacts of the reading (an
  identifier spelling a string value, two lines held jointly by two needles, a bounded integer
  inside a decimal), leaving five. **One of the five is not a far side**: the vision runbook's
  second `auto` says what that mode does rather than which mode ships, and stays true after another
  becomes the default. That single case refuses both mechanisms this entry proposed, since counting
  a value's occurrences on a line cannot be told that one of them makes no claim about the default,
  and rewording was refused as the gate editing what it watches. **The entry's premise was also
  wrong**: a needle carrying words of a sentence is not forbidden, the tree having held
  `` `1024` is the default, paired with `` since the legibility sort, so the four became four
  needles. Two of them are the shape this entry did not predict, where the registry held the
  Meaning cell's explanation and left the **Default cell** free, on the GPU runbook's layer row and
  its two reasoning rows. `shippedcouplings.py` hit the 300-line cap on the way, so one capture's
  own numbers moved to `scripts/capturecouplings.py`, an eighth part costing one import and one
  name. Twenty three planted drifts each exited 1 and each restoration returned the gate to green,
  with three controls staying green, tabled in the ADR-0029 second-spelling addendum. Two residues:
  the matcher edge the reading tripped over
  ([R-398](398-a-rendered-integer-is-a-token-inside-a-decimal.md)), and the fact that this reading
  only sees lines a needle already matches, which is the general question already filed
  ([R-397](397-nothing-counts-what-the-registry-does-not-name.md)).
