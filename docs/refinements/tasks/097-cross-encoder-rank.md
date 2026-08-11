# A cross-encoder rank

**Status:** open, fix when it bites
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** A measured shortfall of the judge on a real corpus, or a latency budget it cannot meet.

Recorded inside the ranked-recall entry, as one of the two deferrals that close opened when the
model rank, the blended key and the recall trail landed together:

> Still open here: a **cross-encoder** rank, which is the other form of a model reranker
> and wants a scoring-model port rather than a chat completion, so it is a new adapter and not a
> policy (trigger: a measured shortfall of the judge on a real corpus, or a latency budget it
> cannot meet);

The relevance-floor decline named it again as the candidate signal:

> **Reopens** behind an embedder whose populations separate, or on a
> signal that is not an absolute cosine; the already-filed **cross-encoder** rank is the candidate,
> since it reads the pair rather than measuring the distance.

## Trail

- 2026-08-06: Opened by the ranked-recall close as the other form of a model reranker, wanting a
  scoring-model port rather than a chat completion and so a new adapter rather than a policy. It was
  one of the two that close opened and that neither the index cell nor the area header picked up
  until the arithmetic correction later the same day took the area's count from 7 to 9.
- 2026-08-08: Named as the candidate when the geometric relevance floor closed as declined on
  measurement, since a cross-encoder reads the pair rather than measuring an absolute cosine, which
  is the signal the calibration showed cannot separate the answerable from the unanswerable.
