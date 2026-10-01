# Flash-Next's first prompt step is a 54-token checkpoint

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-10-01

At the shipped 24g cap Qwen3.8-Flash-Next's first delta for the 3400-word prompt came at 198.0 s
at the default prompt batch and at 163.9 s at a batch of 8192, against the 120 s stall bound
([Qwen3.8-Flash-Next](../../readings/flash-next.md)). In both runs the server's first step was 54
tokens long, because llama-server stores a context checkpoint there for a model whose memory cannot
drop part of a sequence. That step took 58.3 and 59.1 s, and in run E it read about 12 GB of
experts from the mount. At a batch of 8192 the one step after it took 97.2 s and the two tail
steps 7.6 s.

`--ctx-checkpoints 0` may remove the 54-token step. Whether the first token then clears the bound
depends on how much the single step reads once the checkpoint step no longer brings experts in
first: 24.5 to 37 GB at the 250 MB/s run E read is 98 to 148 s. Without checkpoints a hybrid
model reuses no part of an earlier prompt, so every turn of a deep phase would evaluate its whole
prompt again.

What would close it, with the command, price, rule and prediction written here before each draw:

1. One load of run E's argv (`measurements/flash-batch-2026-10-01/flashbatch.py`) with
   `--ctx-checkpoints 0` added, the same cap and watchdog, then the first delta of the same prompt
   against the 120 s bound, with the server log read for the steps it took.
2. If that clears, the same load at the deployed context of 16384 (`CORTEX_CTX_SIZE_BRAIN`), since
   every Flash-Next row so far ran at 8192, and then the decode, stop and injection rows.

Counting progress chunks against the stall bound needs no engine change and already clears both
runs ([763](763-the-stall-bound-times-a-whole-prompt-evaluation-as-one-silence.md)).

## History

- 2026-10-01: filed by
  [735](735-flash-nexts-feasibility-row-is-not-complete-at-the-shipped-memory-cap.md), whose
  run E at a prompt batch of 8192 still began with the 54-token checkpoint step.
