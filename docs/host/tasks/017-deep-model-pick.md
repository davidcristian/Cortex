# The deep-model pick

**Status:** done 2026-08-04
**Session:** gpu-tier-scale
**Capability:** G
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

The pick is **gemma-4-31B-it-qat-q4_0**. It no longer blocks items 2, 3, 4 and 5.

**The measurement has left this directory**, which is what the exit contract in
[index.md](../index.md) asks of a completed item: its home is decision 8 of
[ADR-0004](../../adr/ADR-0004-model-lineup.md), its readings are in
[model lineup](../../readings/model-lineup.md), and the two Brain rows are in
[runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md), with the artifact named in the
`CORTEX_MODEL_FILE_BRAIN` comment of `docker/docker-compose.gpu.yml`. Only the heading and this
record stay here, because four items below are written against this one's number.

**What it found.** All four candidates loaded and served alone on a card that holds the tiers, so
the fit question this item was written to answer turned out not to be the question: the spread was
14607 to 19128 MiB with the cortex evicted, and ADR-0004's hybrid `-ngl` and CPU-KV fallback is not
needed. What separated the candidates is whether they stop reasoning. Both mixture-of-experts
artifacts, the fast ones at about 80 tok/s, consume the entire 8192-token context on an
escalation-grade question and return an empty `content`, and they do it under the deployment's own
conditions, since the brain sends no `max_tokens` and llama-server defaults to `n_predict = -1`.
Both dense candidates answer. The pick loads in 99.6 s, sits at 19128 MiB at the shipped 8192
context and 19786 at 16384, generates at about 31 tok/s, and was the only candidate to answer all
four questions inside a bounded budget. `Qwen3.6-27B-GGUF (Q4_K_M)` is the recorded alternate,
2.7 GB lighter and one question short.

**What this hands the items below.** Item 4 compares a real swap's load phase against **99.6 s**
cold, which leaves the shipped `CORTEX_SWAP_LOAD_TIMEOUT_S` default of 300 s about two thirds
unspent, and against a warm reload of the same artifact at 66.4 s. Item 2's eviction arithmetic is
19128 MiB for the deep tier against a card reading 1867 to 1932 MiB with nothing loaded. The swap
back was also run by hand once: the deep tier stopped in 0.92 s and the cortex was READY again
35.7 s later, with both container health checks green throughout.

**One correction to the shared bring-up.** Its warning about `reasoning_content` is right and is
worth strengthening: a budget that fits a chain of thought plus an answer is not a fixed number, it
is a property of the candidate, and on two of these four no budget inside the context window is
enough. Read `finish_reason` before reading either field. `"length"` with an empty `content` and a
full `reasoning_content` is a model that never finished, and at tier scale that is a finding about
the model rather than about the budget.

## History

- 2026-07-19: filed as the first item of this session when host work was moved out of the ROADMAP's
  slice statuses, blocking the tier-scale swap, the chaos kill, the timings and the
  injection-harness run. Until a pick existed, naming no deep artifact left that tier answering 404
  with boot recovery logging one, which is a stock stack behaving correctly rather than a fault.
- 2026-08-04: run by the agent, driven straight at the model host's control API once per candidate,
  with neither escalation nor the overlay involved. The development machine reported 24463 MiB and
  every candidate loaded and served alone on it, which disproved the premise the item had been filed
  under, that the repo is developed on an 8 GB card. Figures taken on that card stay true of it,
  ADR-0030's measurement of `gemma-4-12b-it-qat-q4_0.gguf` alone at 7715 of its 8188 MiB included.
- 2026-08-04: the first item to leave this directory, and the run that retired the 24 GB capability
  as a reason on its own to file work here, since AGENTS.md already counts GPU work reachable
  through Docker as the agent's to do now. Its exit is also what made the index qualify its exit
  contract: a completed item leaves its content but keeps its number for as long as anything still
  depends on it.
