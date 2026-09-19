# A second occurrence of a value shares a line the registry already covers

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`docs/runbooks/vision.md` line 53 writes `2048` twice: once in the table's Default cell, which the
registry matches by the whole of that row, and once in the sentence after it, which calls that
number the brain half of the pair that makes a 4K screen legible. Both state the shipped edge and
both become wrong when it moves. Only the first is checked, and because a match is a presence test
the second could change to any number with the check still passing, leaving one line naming two
different shipped edges.

The same shape closed on the other value rather than opening here, because that one had a
structural boundary available: the GPU runbook's Example cell contains nothing but the number, and
cell boundaries fix a value without fixing a word of the sentence. The vision runbook's second
occurrence has no such boundaries, so any search text reaching it has to include four words of an
explanation.

The three ways out are each a decision rather than a row. Counting the line's occurrences ties the
Default cell and the sentence into one set, which is true here and false as soon as a third
occurrence arrives for a different reason. Rewriting the sentence to reach the value through a
shape the registry already matches means editing prose to suit the check. Matching a value's
occurrences within one line is a change to `couplings.py` and to the scan, and is the only one of
the three that generalises.

## History

- 2026-08-23: opened by the close of
  [R-382](382-the-paired-numbers-quoted-in-prose.md), which registered both cells of the GPU
  runbook's row and could not cover the vision runbook's second occurrence by any search text that
  fixes the number rather than the sentence.
- 2026-08-23: closed as four ordinary matches and no new mechanism, the population having decided
  it. Eleven checked lines have a leftover occurrence; six are artefacts of the reading (an
  identifier writing a string value, two lines matched by two search texts, a bounded integer
  inside a decimal), leaving five. One of the five is not registrable: the vision runbook's second
  `auto` says what that mode does rather than which mode ships, and stays true after another
  becomes the default. That single case rules out both mechanisms this entry proposed, since
  counting a value's occurrences on a line cannot exclude the one that makes no claim about the
  default, and rewriting was rejected because it means editing prose to suit the check. The
  entry's premise was also wrong: a search text containing words of a sentence is not forbidden,
  the tree having used `` `1024` is the default, paired with `` since the legibility sorting, so
  the four became four search texts. Two of them are a shape this entry did not predict, where the
  registry matched the Meaning cell's explanation and left the Default cell free, on the GPU
  runbook's layer row and its two reasoning rows. `shippedcouplings.py` hit the 300-line cap on
  the way, so one capture's own numbers moved to `scripts/capturecouplings.py`, an eighth part
  costing one import and one name. Twenty five planted changes each exited 1 and each restoration
  returned the check to passing, with three controls staying green. Two residues: the matcher edge
  the reading tripped over ([R-398](398-a-rendered-integer-is-a-token-inside-a-decimal.md)), and
  the fact that this reading only sees lines a search text already matches, which is the general
  question already filed ([R-397](397-nothing-counts-what-the-registry-does-not-name.md)).
