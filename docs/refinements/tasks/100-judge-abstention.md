# A considered abstention reads as a failed rank

**Status:** landed 2026-08-07
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Four of the
26 questions have no answer anywhere in the corpus, and the model got all four right: asked which
notes help, it replied `{"order": []}`, valid and complete rather than truncated, which was
confirmed by re-sampling each fallback and reading the raw text rather than inferring it from the
basis. `JudgeRecallPolicy.select` treats an empty parse as a failure, so all four fell back and
the caller got the cosine's top three irrelevant notes instead. The one thing the judge can do
that no geometric policy can, decline to answer, is the one thing the policy cannot express, and
at the port it looks exactly like an unreachable model. **Cost:** not behind the unchanged seam
in the cheap sense. A third `RankBasis` (an abstention distinct from `VERDICT` and from the
fallback bases) plus a `select` that returns an empty `Ranking` changes what a recall may hand a
turn, so the recaller, the audit trail and the prompt assembly each need to mean something by
zero hits. **Trigger:** flipping the default to `judge`, since the defect is invisible while the
policy is off, or the first report of memory answering a question it has nothing about.
**Landed 2026-08-07 ahead of its trigger** ([ADR-0038](../../adr/ADR-0038-ranked-recall.md)
abstention addendum), because the fix is small and the entry's own reason for deferring it was the
blast radius, which the code did not confirm. `RankBasis` gained `DEMUR`, the judicial sibling of
`VERDICT` for a reader who decided that nothing in the pool makes the case (a demurrer grants
every word of the material and still finds no case; `NONSUIT` was more exact and less readable,
`SILENCE` would have fitted an empty store as well as a refusal, and `ABSTAIN` says no decision
was made, which is the opposite of what happened). `parse_order` now has three outcomes rather
than two: `None` for a reply nothing can be read out of, **including one that named notes of which
none exists**, since a model that tried to pick and produced nothing pickable has failed rather
than declined; `()` for an `order` that arrived empty; and the picks otherwise. `select` returns
`Ranking(hits=(), basis=DEMUR)` for the middle case and never consults the fallback, which stays
exactly where it was for real failures. **Cost correction:** this entry priced three consumers
needing to mean something by zero hits, and two of the three already did. `MemoryRecaller.recall`
returns `ranking.memories`, so an empty ranking was already an empty sequence and nothing
re-fetched or substituted the pool; `_recalled_context` (`turn_context.py`) already returned
`None` on no hits, so the turn was already assembled without a memory block. Only the trail needed
the new basis, and it needed no new field for it, since `demur` with no hits, another basis with
no hits, and a fallback's basis with hits are three readings of fields the line already carried.
What the entry did not price and the close added is an invariant: a `DEMUR` ranking carrying hits
is rejected at construction, because a policy cannot both decline and return something. CI-gated at
100% over the fakes, with the empty-pick path proved able to fail by restoring the old
`if not order` branch (three tests fail, including the turn-assembly one). **Measured live on
the same 41-note corpus that found it**: the four unanswerable questions now return nothing, 4 of
4, the whole run fell back 0 of 26 where it fell back 4 of 26, and the ranking on the 22
answerable questions is unchanged (aggregate MRR 1.000 against the cosine's 0.902, the
reversed-cosine control still 0.000) at 0.76 s per recall. Declining costs what ranking costs,
because the pool prompt is evaluated either way.

## Trail

- 2026-08-06: Opened by the widened corpus, taking the area from 9 to 10. The measurement that
  vindicated the policy is the measurement that found the hole in it, which is the argument for
  widening a corpus even when the recommendation is already written.
- 2026-08-07: Landed ahead of its trigger, the entry's stated cost having been the reason to wait
  and the tree not confirming it. Two of the three consumers it priced already meant the right thing
  by zero hits, so what was left was the `DEMUR` basis, a `parse_order` with three outcomes rather
  than two, and one branch in `select`. The area held at 10, one out and one in, and the pair is
  written out because a count right by cancellation is the failure this backlog warns about.
