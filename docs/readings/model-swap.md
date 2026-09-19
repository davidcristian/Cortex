# Readings: what a model swap costs

How long the model host's control calls take and what a handoff's swap costs end to end. Cited by
[ADR-0030](../adr/ADR-0030-brain-handoff.md) (the risk on swap latency, the drain bound),
[ADR-0053](../adr/ADR-0053-model-host-supervisor.md) decisions 3 and 11 (the stop bounds and their
pairing) and [ADR-0055](../adr/ADR-0055-co-residency-and-spill-watch.md). The procedures that take
these readings are in the [model-swap](../runbooks/model-swap.md) runbook.

## A handoff at tier scale

**2026-08-07**, 24 GB card, the shipped cortex (gemma-4-12B QAT q4_0) and deep pick (gemma-4-31B QAT
q4_0), artifacts warm in the page cache, through the real `model-host` control API: stopping the
cortex took 0.7% of the deep model's time to reach `ready` (0.48 s against 70.03 s), stopping the
deep model 1.3% of it (0.89 s), and bringing the cortex back 45% of it (31.43 s). The swap both ways
was 1.47 times the deep load alone (102.9 s). A cold deep load, 99.6 s from start to `READY` in
[ADR-0004](../adr/ADR-0004-model-lineup.md)'s lineup, makes the swap about 1.9 times the warm load.
Method: timed `start`, `stop` and `status` polls against the control API.

## What an eviction costs

**2026-07-18**, 8 GB card, small stand-ins (`Qwen3.5-0.8B-Q8_0` as the cortex tier,
`Qwen3.5-2B-Q4_K_M` as the deep one, `--ctx-size 4096`): stopping an idle child took 0.10 to 0.40 s,
while the two loads took 11.3 and 18.0 s, so the load is the whole cost. Stopping a child with a
request in flight took 10.09 s and 10.90 s: `llama-server` logged `cleaning up before exit` and did
not exit, because the shipped tiers run `--parallel 1`, so the whole 10 s SIGTERM grace was paid and
the child was killed. A busy eviction therefore costs about 25 times an idle one on that card.
Method: `POST /models/{model}/stop` timed with and without a stream in flight, VRAM read with
`nvidia-smi`.

## A stop queued behind a status

**2026-07-18**, 8 GB card, a SIGSTOPped child on the shipped grace: a stop took 10.89 s with the
per-model lock free and 15.70 s when issued 0.2 s behind a status, the status itself taking 5.80 s
(the probe timeout plus overhead). So the worst stop is the probe timeout plus the grace plus the
reap bound, which is why all three enter the pairing rule. Method: concurrent `status` and `stop`
against a stopped process.

## The fit check and the unhosted refusal, live

**2026-08-07**, 24 GB card: with the cortex resident the sidecar reported 61% of the card free
(14905 of 24463 MiB) against a declared deep cost of 78% of it (19125 MiB), and the swap in refused
in 0.03 s with nothing started; with the cortex evicted, the same call passed and the deep model
reached `ready` in 69.24 s, leaving 15% of the card free. Method: `test_model_host_live.py`,
integration-marked.

**2026-08-16**, 24 GB card, a sidecar whose roster held only the cortex: before the refusal a
handoff stopped the cortex, met a 404 on the deep tier and reloaded the cortex, 29.7 s with no
tier serving; with the refusal the conductor made one `GET /models/brain` and answered in under
0.01 s with the cortex serving throughout. Method: the real `SwapConductor` over the real
`HttpModelHost` and sidecar image.

## An undersized card does not fail

**2026-07-19**, 8 GB card, the cortex evicted and the deep tier pointed at a 17 GB artifact:
llama.cpp logged `failed to fit params to free device memory`, kept every layer on the GPU, and the
tier reached `READY` after 373 s, 1.24 times the 300 s load bound, then generated 16 tokens in 36 s.
The driver paged into host memory rather than refusing, so a tier-scale swap on a card too small
for it looks like a pass with meaningless numbers. Method: a manual start through the control API.
