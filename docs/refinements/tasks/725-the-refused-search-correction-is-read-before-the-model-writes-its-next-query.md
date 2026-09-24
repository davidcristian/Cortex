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

**Pre-registered 2026-09-24.** `test_the_refused_search_query_written_after_the_folder_listing`
in the same file draws the refused-search turn on seeds 0 to 19 in each of the three variants, one
pytest process and one load, with the cortex flags as shipped and the prompt cache on as the file
leaves it. A draw whose calls include `list_folders` and no `search_emails` is drawn once more on
the same seed, with that call answered by the sidecar's own listing, stamped untrusted as the
dialect row stamps it (`answers_listing` in `correction_reads.py`); every other draw is scored as
it is. `score_refused_search` scores the reply that results, so a second listing scores `other`.
The deciding count is the harness's `followed`, unfenced against bare: the unfenced variant reads
above the bare failure when a two-sided Fisher exact test on the twenty draws each reads p below
0.05. Against a bare count of 12 that needs 19 or more, and at a bare count of 16 or more no
unfenced count can read above it. Every scored query is read by hand, and the count that keeps the
sender as a `FROM` criterion is reported beside the harness's without deciding. Predicted, with a
90% range: unfenced 17 (12 to 20), fenced 16 (11 to 20), bare 13 (7 to 18), not apart; draws
continued past the listing 18, 14 and 18 (each within 3).

## History

- 2026-09-24: opened by
  [R-713](713-the-reworded-email-corrections-are-unmeasured-across-the-three-variants.md), whose
  draws mostly listed the folders before searching again.
