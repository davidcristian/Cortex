# The embedder names its artifact outside the family the naming rule enforces

**Status:** landed 2026-08-30
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-29 by the close of
[R-472](472-the-membership-prefix-is-a-convention-nothing-enforces.md), which made
`CORTEX_MODEL_FILE_` the spelling every model artifact this tree names must carry, so that the
membership of the subagent set is decided by a name rather than assumed from one.

The rule has one exclusion that is a live counterexample to it. `docker-compose.memory.yml` starts
the CPU embedder from the same llama.cpp image as the subagent servers and names its artifact
`CORTEX_EMBED_MODEL_FILE`, in a different word order and outside the family. The gate does not see
it because that argv declares `--embeddings`, which is honest as far as it goes: a server serving
no chat can never be a subagent, and the exclusion cannot be walked through by the fault it sits
beside, since adding the flag to a chat server would stop it serving chat.

**What the exclusion still costs.** The tree now spells its artifacts two ways, and the rule
enforces one of them. An author adding a server by copying the block that is closest to what they
are building copies whichever they land on, and the embedder's block is the one a new non-chat
model server would be copied from. The convention the naming rule exists to make readable is
therefore readable everywhere except in the one file that would teach a newcomer the other shape.

**Why it was left.** Renaming it to `CORTEX_MODEL_FILE_EMBED` changes an operator-facing variable
to satisfy a gate. A deployment whose own `.env` names the old variable would keep starting, fall
back to the shipped nomic pick and load a different model in silence, which is a worse failure
than the one being closed, and it is the failure mode the naming rule in
[AGENTS.md](../../../AGENTS.md) warns about for any key something outside this repo may already
depend on. It also mixes a production config change into a gate's own commit.

**What would close it.** Either the rename, done deliberately and with the old spelling kept
working for a release (a compose default that reads the new variable and falls back to the old one
is the cheap shape, and a runbook line saying so is the rest of it), or the argued decision that
an artifact serving no chat is a separate family whose own spelling is `CORTEX_EMBED_MODEL_FILE`,
written down where the rule is so the next reader finds the reason rather than the exception.
The second is cheaper and should be argued against before the first is built, since a family of
one is a rule with an example rather than a rule.

## Trail

- 2026-08-29: opened by the close of
  [R-472](472-the-membership-prefix-is-a-convention-nothing-enforces.md), whose naming rule
  excludes this artifact by what its server serves rather than by what it is called.
- 2026-08-30: landed as the rename, recorded in the [ADR-0029 addendum on a non-chat artifact
  naming itself in the
  family](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-30-a-non-chat-artifact-names-itself-in-the-family-and-the-exclusion-retires),
  with a pointer addendum at [ADR-0004](../../adr/ADR-0004-model-lineup.md). The variable is
  `CORTEX_MODEL_FILE_EMBED`, and the `--embeddings` exclusion in `scripts/artifactnames.py` is
  gone rather than left inert. **This entry's preferred close was refused on the tree's own
  evidence.** A separate family for non-chat artifacts is not a family of one and never was: the
  multimodal projector is a non-chat model artifact too and is named `CORTEX_MMPROJ_FILE_CORTEX`,
  in the family's word order with one word swapped, so the split is a word order and not a
  category, and the embedder was simply the spelling nobody had revisited. **The exclusion was
  also worse than this entry said**, which the mutation table measures: a second non-chat server
  copied from that block and named `CORTEX_RERANK_MODEL_FILE` left the gate printing OK over five
  artifacts and exiting 0, so the exclusion was a door rather than one artifact's dispensation.
  **The shim this entry called the cheap shape was measured rather than assumed**: compose does
  expand `${NEW:-${OLD:-pick}}` (v2.39.1), which is the opposite of what
  `scripts/composedefaults.py` claimed and is corrected there, but that reader refuses a nested
  form and three gates walk it over the line, so the shim was declined and the reader's question
  filed as
  [R-502](502-the-substitution-reader-refuses-a-nesting-compose-expands.md). The rename's risk is
  bounded instead: no `.env` is tracked or present here, the fallback lands on the pick almost
  every host already runs, and `docs/runbooks/memory-pgvector.md` carries the migration. The
  projector's own unheld spelling is
  [R-501](501-the-projector-is-named-in-a-sibling-family-nothing-holds.md).
