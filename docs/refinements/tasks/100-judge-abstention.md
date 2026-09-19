# A considered abstention reads as a failed rank

**Status:** done 2026-08-07
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Four of the widened corpus's 26 questions have no answer anywhere in it, and the model got all
four right: asked which notes help, it replied `{"order": []}`, valid and complete rather than
truncated, confirmed by re-sampling each fallback and reading the raw text. But
`JudgeRecallPolicy.select` treated an empty parse as a failure, so all four fell back and the
caller got the cosine's top three irrelevant notes. The one thing the judge can do that no
geometric policy can, decline to answer, was the one thing the policy could not express, and at
the port it looked exactly like an unreachable model.

**Shipped 2026-08-07 ahead of its trigger**
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) decision 11), because the fix is small and the
entry's reason for deferring it, the number of consumers it would touch, was not borne out by the
code.

`RankBasis` gained `DEMUR`, the judicial sibling of `VERDICT`, for a reader who decided that
nothing in the pool makes the case. (`NONSUIT` was more exact and less readable, `SILENCE` would
have fitted an empty store as well as a refusal, and `ABSTAIN` says no decision was made, which is
the opposite of what happened.) `parse_order` now has three outcomes rather than two: `None` for a
reply nothing can be read out of, including one that named notes of which none exists, since a
model that tried to pick and produced nothing pickable has failed rather than declined; `()` for
an `order` that arrived empty; and the picks otherwise. `select` returns
`Ranking(hits=(), basis=DEMUR)` for the middle case and never consults the fallback, which stays
where it was for real failures. A `DEMUR` ranking with hits is rejected at construction, because a
policy cannot both decline and return something.

Two of the three consumers the entry priced already meant the right thing by zero hits.
`MemoryRecaller.recall` returns `ranking.memories`, so an empty ranking was already an empty
sequence, and `_recalled_context` in `turn_context.py` already returned `None` on no hits, so the
turn was already assembled without a memory block. Only the trail needed the new basis, and it
needed no new field, since `demur` with no hits, another basis with no hits, and a fallback's
basis with hits are three readings of fields the line already had.

Covered at 100% in CI over the fakes, with the empty-pick path proved able to fail by restoring
the old `if not order` branch, which fails three tests including the turn-assembly one. Measured
live on the same 41-note corpus that found the problem: the four unanswerable questions now
return nothing, 4 of 4; the whole run fell back 0 of 26 where it had fallen back 4 of 26; the
ranking on the 22 answerable questions is unchanged (aggregate MRR 1.000 against the cosine's
0.902, the reversed-cosine control still 0.000) at 0.76 s per recall. Declining costs what
ranking costs, because the pool prompt is evaluated either way.

## History

- 2026-08-06: Opened by the widened corpus, taking the area from 9 to 10. The measurement that
  confirmed the policy is the measurement that found the hole in it.
- 2026-08-07: Shipped ahead of its trigger. The area held at 10, one out and one in, and the pair
  is written out because a count that is right only by cancellation is a failure this backlog
  warns about.
