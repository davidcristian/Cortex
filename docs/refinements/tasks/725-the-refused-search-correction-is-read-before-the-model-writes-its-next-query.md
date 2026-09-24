# The refused-search correction is read before the model writes its next query

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-09-24

`test_the_refused_search_correction_across_the_three_variants` in
`test_unfenced_correction_live.py` scores the first reply after the refused search. On 2026-09-24
that reply was a `list_folders` call in 18, 14 and 18 of 20 draws of the unfenced, fenced and bare
variants, and each of those draws scores `other`
([untrusted-framing](../../readings/untrusted-framing.md#a-sidecars-correction-fenced-and-unfenced)).
The model has not yet written a query in those draws, so what `SEARCH_REFUSED` does to the query it
writes after the listing is unmeasured. The row's counts, 2, 6 and 2 of 20, say only how often the
model searches again at once.

**What would close it.** A row that answers each draw's `list_folders` call with the sidecar's own
listing, as `test_the_dialect_the_cortex_writes_its_first_query_in` does, and scores the next
`search_emails` query with `score_refused_search`, three variants on the same twenty seeds, with the
depth, the deciding count and a Fisher rule fixed in this file before the card runs. If the
unfenced variant then reads above the bare failure, decision 10 of ADR-0013 names the correction as
a reason again.

## History

- 2026-09-24: opened by
  [R-713](713-the-reworded-email-corrections-are-unmeasured-across-the-three-variants.md), whose
  draws mostly listed the folders before searching again.
