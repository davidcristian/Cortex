# The recall policies restate what they share, one policy at a time

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)
**Verified:** 2026-09-17

Opened 2026-09-17 by the trigger sweep over
[R-018](018-ports-without-contract-suite.md), which enumerated the Python ports by grep instead of
from the inventory table at the origin and found `RecallPolicy` missing from it.

`RecallPolicy` (`brain/packages/core/src/cortex_core/rerank.py:28`) is a port with five shipped
implementations and no fake: `RawRecallPolicy` in `rerank.py`, `RerankingRecallPolicy`,
`MmrRecallPolicy` and `RecencyMmrRecallPolicy` in `rerank_policies.py`, and `JudgeRecallPolicy`
in `rerank_judge.py`. `docs/modules/brain-core.md` calls it a port. Its tests are written one
policy at a time in `core/tests/test_rerank.py` (41 tests) and `test_rerank_judge.py` (29), and
the obligations the policies share are restated under each policy's name rather than held once:

- "over-fetches a wider pool" for the reranking, MMR and recency MMR policies;
- "of an empty pool is empty" for the same three;
- "returns all when the pool is smaller than k" for MMR and recency MMR;
- "rejects a pool factor below one" for the same three as the first.

`RawRecallPolicy` is named in none of those four, and recency MMR carries the rule that a
zero-magnitude embedding is never counted redundant only through the `greedy_mmr` it shares with
MMR (`rerank_math.py:43`), with no test of its own naming it. A check added for one policy reaches
the others only if someone writes it again, which is the defect the origin's contract-test sweep
exists to end.

**What would be built.** A `recall_policy_contract.py` beside `test_rerank.py` holding the
obligations the port's docstring states or implies (`candidate_k(k)` is at least `k`, `select`
reorders and prunes the pool it was handed so every hit it returns came from that pool, at most
`k` come back, an empty pool gives an empty answer, and a policy that runs a model pass has closed
its stream when `select` returns), and one driver parametrized over the five, with each policy's
own suite keeping what only that policy does. The docstring says nothing about a pool smaller
than `k`, and a deduplicating policy may legitimately answer fewer than a non-deduplicating one,
so decide that difference against the port's description the way the other lists did, and write
the decision into the docstring rather than into one policy's tests. The judge policy needs a scripted inference backend, which
`ScriptedInferenceBackend` already provides. Add a `RecallPolicy` row to the origin's table in the
same change.

**Not built on the day it was filed** because every file it touches is under
`brain/packages/core/`, which was held unchanged that night for a GPU sitting that re-imports the
core package row by row.

## Trail

- 2026-09-17: filed by the trigger sweep over
  [R-018](018-ports-without-contract-suite.md), from the origin's addendum of the same day that
  re-read the port inventory against every protocol.
