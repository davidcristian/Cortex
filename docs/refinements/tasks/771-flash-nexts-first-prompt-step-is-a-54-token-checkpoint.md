# Flash-Next's first prompt step is a 54-token checkpoint

**Status:** done 2026-10-02
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

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

Step 1, written on 2026-10-02 before the draw. Command: `python3
measurements/flash-ckpt-2026-10-02/flashckpt.py` from the repo root under its `launch.sh`, which is
run E's driver with `--ctx-checkpoints 0` added and nothing else changed (24g cap, batch 8192,
`-lv 4`, `scripts/memwatch.py`, 360 s cut, 5 s card, mount and memory samples). Price: a 140 to
210 s load and at most 360 s of request, about 8 minutes and at most 12. Rule:

- If the server log still shows a 54-token first step, the flag is not what splits the prompt
  there: the remedy above is wrong, step 2 is not drawn, and this task stays open on what does.
- If the step is gone and the first delta comes at 120 s or less, step 1 clears and step 2's
  first row, the same argv at a context of 16384, goes into the next detached card run.
- If the step is gone and the first delta comes after 120 s, the checkpoint step is not what
  keeps the first token past the bound at the 24g cap; step 2 is not drawn and this task closes.

Nothing ships on either result, since Flash-Next is not deployed. Prediction: the 54-token step is
gone (0.8), the prompt goes in one step that reads 24.5 to 36.5 GB, and the first delta comes at
128 s (100 to 150), past the bound (0.6).

Counting progress chunks against the stall bound needs no engine change and already clears both
runs ([763](763-the-stall-bound-times-a-whole-prompt-evaluation-as-one-silence.md)).

## History

- 2026-10-01: filed by
  [735](735-flash-nexts-feasibility-row-is-not-complete-at-the-shipped-memory-cap.md), whose
  run E at a prompt batch of 8192 still began with the 54-token checkpoint step.
- 2026-10-02: step 1 drawn under the rule above as run F of
  [the readings](../../readings/flash-next.md#context-checkpoints-off-2026-10-02). The server logged
  `context checkpoints disabled` and took the prompt in one 6184-token step that read 33.9 GB from
  the mount, and the first delta came at 186.8 s, 1.56 of the bound, at an SM clock of 0.59 of the
  maximum. The 54-token step is gone and the first token still misses the bound, so step 2 is not
  drawn and this task closes. The prediction held on the step and the read and missed on the time,
  the mount reading at 0.77 of run E's rate on a load as slow as run C's first.
