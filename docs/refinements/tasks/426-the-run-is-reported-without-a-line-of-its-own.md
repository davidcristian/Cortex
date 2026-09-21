# The matched run has no line of its own, though choosing between matches computes one

**Status:** done 2026-08-25
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

An unmatched search text has two readings and they are told in two different ways. The value
reading says how many places contain the value, which line the nearest one is on, and what that
line says. The run reading, the longest opening piece of the search text the file contains
anywhere, is quoted as text alone. Where in the file that run stops is never said, even though
`searchtexts.nearest` locates every occurrence of it in order to pick which value match to quote,
and then discards the positions.

The distance between the two is the evidence a reader is weighing. A value on the line where the
run stops is the strong form of "what moved is the surrounding shape". A value seventy lines away,
which is the real case this came out of, is the weak form, and the reader can only tell which they
have by opening the file.

Giving the run a line raises a question the value reading did not have to answer: a run is a
prefix, so it can appear in several places. Naming one line therefore has to say which, and the
answer may be the last occurrence, the one nearest the quoted value, or a count.

## History

- 2026-08-25: opened by the close of
  [R-414](414-the-still-spelled-reading-does-not-say-where.md), which used the run's positions to
  choose which value match to quote and never used them on the run itself.
- 2026-08-25: closed. The three candidates for which occurrence to name turned out not to be a
  choice: the two readings are the two ends of one distance, so `searchtexts.nearest` picks the pair
  and both halves are reported, each named as the one nearest the other, with the same fallback to
  the first occurrence stated explicitly when one of them is missing. The run's line goes in the
  clause it already had, with a count when the file contains the run more than once, worded in the
  value reading's own three shapes. The distance is not computed for the reader: two line numbers
  are the comparison, and a gap stated in lines would sometimes disagree with a pair chosen by
  distance in characters. No second quoted line, the entry's own cheapest option, measured at 66
  characters added to a message of 788. Reading the positions out found a correction underneath:
  the code anchored where the run starts while the prose said it stopped there, which biases every
  choice towards the text above the difference, and no case in the tree could tell the two apart
  until this entry added one. Four mutations over `scripts/tests/test_crosscheck.py`, 144 cases, in
  [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md).
