# A counted match that finds nothing gets none of the detail a presence test gets

**Status:** done 2026-09-12
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`scripts/crosscheck.py`'s `check_mention` branched on whether the match has an occurrence count. A
match without one raised through `searchtexts.unfound`, which says whether the file still writes the
constant's own value and how much of the search text it contains. A match with a count raised the
older sentence, `found 0, pinned 2; move the whole set, or correct occurrences in the registry`,
which is true and says nothing about which of the search text's literals moved. Zero found is
exactly the case the detailed reading was written for, and there are counted matches over search
texts containing several of a neighbour's digits: `docs/runbooks/body-volume.md`'s
`host.docker.internal:{value}` and `CORTEX_BODY_ADDR=0.0.0.0:{value}` are both set to two
occurrences (`scripts/endpointcouplings.py`).

It was left out of the close that built the detailed reading because the counted branch's message
is asserted word for word by the suite, so the change is a message edit plus a test edit plus a
branch, in a close whose subject was the presence test. Nothing was waiting on it: no counted match
has ever gone to zero on the real tree.

## History

- 2026-08-23: opened by the close of
  [R-403](403-a-needles-literal-reddens-the-wrong-entry.md), which made an unmatched search text's
  message name whose literal stopped matching, and wired that into one of the two branches that can
  find nothing.
- 2026-09-10: read against the tree and still not fired. `check_mention` still branched on
  `wanted is None`, still sent only the uncounted branch through `searchtexts.unfound`, and the
  counted branch still raised the sentence above. The two counted matches over
  `docs/runbooks/body-volume.md` are still set to two occurrences in `scripts/endpointcouplings.py`,
  with three more counted matches beside them. Nothing has gone to zero: `crosscheck` passed over 91
  constants, 109 declaring places and 296 matches, 25 of them with a count.
- 2026-09-12: closed ahead of its trigger, which has still not fired. `check_mention` now tests
  `found` before the count, so a file containing none of the search text gets `searchtexts.unfound`
  whether or not a count is set, and the count follows as its own clause, `the registry pins 2
  occurrences, so move the whole set, or correct occurrences in the registry`. No sentence states a
  number of occurrences the file did not have. A count that is wrong without being zero still gets
  `found N, pinned M`, which is the one reading a run and a still-present value cannot improve on:
  the text is there and the question is how many. The advice both messages end on is now one
  string, `crosscheck.RECOUNT`. The trade this entry recorded was smaller than it reads: one
  branch, one shared constant, one suite assertion re-aimed from the count sentence to the reading,
  and one test written to drive the new branch. Four planted changes on the real tree before and
  after (ADR-0042 decision 24), two of them a counted match losing its whole set and two controls,
  the short count and an uncounted match, both unchanged. One residue opened, the short count
  naming no line ([R-656](656-a-short-count-names-no-line.md)), which this change made an
  asymmetry.
