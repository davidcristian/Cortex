# Notice a handoff that spilled

**Status:** landed 2026-08-08
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-07 by the fit check's own landing
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) fit-check addendum). The check compares the deep
tier's declared cost against what the card reports free immediately before the load, which is the
only instant at which free memory means anything. Two things stay outside what it can detect. A deployment
that **under-declares** passes the check and spills anyway, because nothing here measures a
model. And memory taken **during** the load (this machine's idle floor moved between 1529 and
2836 MiB inside one session, Windows owning the difference) can turn a fit into a spill after the
check has already answered. In both cases the outcome is the measured one: both tiers report
`ready`, `nvidia-smi` reads about 23.6 GB used and about 0.5 GB free exactly as a genuine fit
does, and the deep model decodes at **14.80 to 17.29 tok/s** against **25.07 to 33.28** with the
card to itself. **The only witness is decode rate, and nothing in the brain watches it.** What
would close it: the deep phase reading llama.cpp's own `timings.predicted_per_second` off the
completion it already streams, comparing it against a rate the deployment measured for that tier
(the same shape as the VRAM figure, and the same honest limitation), and saying so loudly once
per handoff when it collapses. The cost is a backend that surfaces its own timings, which
`LlamaCppBackend` today discards, so it is a port question and not a one-line read. **Trigger:**
any report of a deep phase that is slow rather than absent, on a deployment whose fit check
passed.

**Landed 2026-08-08 ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) spill-watch addendum), ahead of
its trigger and in the shape this entry proposed**, which is rarer here than the alternative and
is worth saying plainly: the entry's account of the code was re-derived before anything was
designed and held. A grep over `brain/packages` for `timings` and `predicted_per_second` found
the strings only inside two live tests' own wall-clock dictionaries, so nothing read the server's
figure, and the port question the entry predicted was the real cost. What landed:
`InferenceEvent` gains a `DecodeCadence` arm that a backend closes its stream with when its
engine reports one (and legitimately omits when it does not, so silence never reads as healthy);
`stream_tool_loop` absorbs it into an optional `CadenceWatch` on the loop context and yields
nothing, a decode rate being a fact about the machine rather than something the turn said; the
watch is pure policy that ignores samples under 32 tokens and judges on the **fastest**
qualifying one, so a briefly busy card cannot trigger it and a tier that never once reached
its floor does; the floor is `CORTEX_SWAP_BRAIN_DECODE_TPS` on `ResidencyPlan`, unset meaning
report and judge nothing; and the deep phase says so once per handoff, at WARNING when it
collapsed and INFO when it did not. Port + contract test driven over both the scripted twin and
the real adapter + fakes, CI-gated at 100%, and the split the cap forced was `backend.py` into
`request.py` (core values onto the wire) and `decode.py` (the wire back). **Measured live on the
24 GB card**, three completions an arm through the shipped adapter and watch: the deep tier alone
reached 31.08 to 33.78 tok/s cold, and with the cortex resident first and the deep model loaded
beside it, which is a co-resident handoff's own order, 20.38 to 22.77, **both tiers reporting
`ready` and the card reading 423 MiB free**. At a declared 25.0 the watch collapsed the second
arm by 2.23 and passed the same tier minutes later once the peer was evicted, so it is not a gate
that always fires (`packages/inference/tests/test_decode_cadence_live.py`, integration-marked).
The entry's **one wrong word was "loudly"**: what the phase does is log, and the two things it
does not do are recorded below as this area's newest entries.

## Trail

- 2026-08-07: Opened by the fit check's own landing and joined the index's fix-when-it-bites bucket
  the moment that check landed, because a reading taken before the load can see neither a figure the
  deployment under-declared nor a gigabyte the desktop takes during it, and the spill it leaves
  reports `ready` on both tiers and reads like a fit on `nvidia-smi`.
- 2026-08-08: Landed ahead of its trigger and in the shape the entry proposed, its account of the
  code re-derived first and held, and its line in that bucket was struck. Measured on the 24 GB card
  at 20.38 to 22.77 tok/s spilled against 31.08 to 33.78 alone, both tiers reporting `ready`
  throughout. It left two entries behind it, a spill that does not change what the next handoff
  promises and a prefill rate nothing reads.
