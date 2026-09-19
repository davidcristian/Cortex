# The embedder names its artifact outside the family the naming rule enforces

**Status:** done 2026-08-30
**Area:** repo-checks
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)

The rule that every model artifact this tree names must begin with `CORTEX_MODEL_FILE_` had one
exclusion that was a live counterexample to it. `docker-compose.memory.yml` starts the CPU embedder
from the same llama.cpp image as the subagent servers and names its artifact
`CORTEX_EMBED_MODEL_FILE`, in a different word order and outside the family. The check did not see
it because that argv declares `--embeddings`, which is true as far as it goes: a server serving no
chat can never be a subagent.

What the exclusion cost is that the tree wrote its artifacts two ways and the rule required one of
them. An author adding a server copies the block closest to what they are building, and the
embedder's block is the one a new non-chat model server would be copied from.

## History

- 2026-08-29: opened by the close of
  [R-472](472-the-membership-prefix-is-a-convention-nothing-enforces.md), whose naming rule excludes
  this artifact by what its server serves rather than by what it is called.
- 2026-08-30: closed as the rename, recorded in the artifact naming decision of
  [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md), with a pointer at
  [ADR-0004](../../adr/ADR-0004-model-lineup.md). The variable is `CORTEX_MODEL_FILE_EMBED`, and the
  `--embeddings` exclusion in `scripts/artifactnames.py` is gone rather than left inert. This
  entry's preferred close, a separate family for non-chat artifacts, was rejected on the tree's own
  evidence: the multimodal projector is a non-chat model artifact too and is named
  `CORTEX_MMPROJ_FILE_CORTEX`, in the family's word order with one word swapped, so the split is a
  word order and not a category. The exclusion was also worse than this entry said, which the
  mutation table measures: a second non-chat server copied from that block and named
  `CORTEX_RERANK_MODEL_FILE` left the check printing OK over five artifacts and exiting 0. The
  fallback this entry called the cheap shape was measured rather than assumed: compose does expand
  `${NEW:-${OLD:-pick}}` (v2.39.1), which is the opposite of what `scripts/composedefaults.py`
  claimed and is corrected there, but that reader rejects a nested form and three checks walk it, so
  the fallback was declined and the reader's question filed as
  [R-502](502-the-substitution-reader-refuses-a-nesting-compose-expands.md). The rename's risk is
  bounded instead: no `.env` is tracked or present here, the fallback uses the pick almost every
  host already runs, and `docs/runbooks/memory-pgvector.md` has the migration. The projector's own
  unchecked name is [R-501](501-the-projector-is-named-in-a-sibling-family-nothing-holds.md).
