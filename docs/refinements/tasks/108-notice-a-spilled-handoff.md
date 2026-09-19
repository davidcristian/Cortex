# Notice a handoff that spilled

**Status:** done 2026-08-08
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)

The fit check ([R-107](107-co-resident-fit-check.md)) compares the deep tier's declared cost
against what the card reports free immediately before the load. Two things stay outside what it
can detect. A deployment that under-declares passes the check and spills anyway, because nothing
measures a model. And memory taken during the load can turn a fit into a spill after the check
has answered: this machine's idle floor moved between 1529 and 2836 MiB inside one session, with
Windows owning the difference. In both cases both tiers report `ready`, `nvidia-smi` reads about
23.6 GB used and about 0.5 GB free exactly as a genuine fit does, and the deep model decodes at
14.80 to 17.29 tok/s against 25.07 to 33.28 with the card to itself. The only sign is decode
rate, and nothing in the brain watched it.

**Shipped 2026-08-08** ([ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md) decision
4), ahead of its trigger and in the shape this entry proposed. A grep over `brain/packages` for
`timings` and `predicted_per_second` found the strings only inside two live tests' own wall-clock
dictionaries, so nothing read the server's figure, and the port change the entry predicted was
the real cost.

`InferenceEvent` gained a `DecodeCadence` variant that a backend closes its stream with when its
engine reports one, and legitimately omits when it does not, so silence never reads as healthy.
`stream_tool_loop` absorbs it into an optional `CadenceWatch` on the loop context and yields
nothing, a decode rate being a fact about the machine rather than something the turn said. The
watch is pure policy: it ignores samples under 32 tokens and judges on the fastest qualifying
one, so a briefly busy card cannot trigger it while a tier that never once reached its floor
does. The floor is `CORTEX_SWAP_BRAIN_DECODE_TPS` on `ResidencyPlan`, and unset means report and
judge nothing. The deep phase logs once per handoff, at WARNING when the rate collapsed and INFO
when it did not. Port and contract test driven over both the scripted twin and the real adapter
plus fakes, covered at 100% in CI. The line cap forced `backend.py` to split into `request.py`
(core values onto the wire) and `decode.py` (the wire back).

Measured live on the 24 GB card, three completions per condition through the shipped adapter and
watch: the deep tier alone reached 31.08 to 33.78 tok/s cold, and with the cortex resident first
and the deep model loaded beside it, which is a co-resident handoff's own order, 20.38 to 22.77,
both tiers reporting `ready` and the card reading 423 MiB free. At a declared 25.0 the watch
reported the second condition as collapsed by 2.23 and passed the same tier minutes later once
the peer was evicted, so it is not a check that always fires
(`packages/inference/tests/test_decode_cadence_live.py`, integration-marked).

## History

- 2026-08-07: Opened by the fit check's own close, and joined the index's fix-when-it-matters
  bucket the moment that check shipped, because a reading taken before the load can see neither a
  figure the deployment under-declared nor a gigabyte the desktop takes during it.
- 2026-08-08: Shipped ahead of its trigger and in the shape the entry proposed, its account of the
  code checked first and confirmed, and its line in that bucket was removed. It left two entries
  behind it: a spill that does not change what the next handoff promises
  ([R-109](109-spill-does-not-latch.md)), and a prefill rate nothing reads
  ([R-110](110-prefill-second-witness.md)).
