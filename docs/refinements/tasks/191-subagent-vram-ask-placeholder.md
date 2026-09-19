# The shipped subagent VRAM request placeholder

**Status:** done 2026-08-08
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

`docker-compose.subagents.yml` set `CORTEX_SUBAGENTS_VRAM_GB=5.5` and the code default was 2.0,
neither of them measured. With the cortex reservation corrected the headroom is 5.4 GiB, so the
request was the only remaining reason the shipped stack refused every GPU placement.

Measured at the shape read out of the running child's argv (`-ngl 99 --ctx-size 8192 --parallel 2
--jinja` with thinking off and no projector), with the cortex resident throughout and `nvidia-smi`
total used sampled every 0.2 s, the tier is 3228 to 3355 MiB idle and costs at most 3410 MiB above a
floor read with it stopped at both ends of the session (10448 to 10500, then 10428 to 10493 MiB,
agreeing within 20 MiB). Twelve requests each filling its slot's whole half of the 8192 KV (3803
prompt tokens plus 293 decoded, exactly 4096) moved nothing beyond the idle band, because this tier
has no vision path.

The request is now 3.5 GiB in both declarations, a margin of 174 MiB, which covers the sampler's
spread and the floor bracket twice over. The reservation was deliberately not rounded down to 8.5 to
make 5.5 fit, which would have left two wrong numbers agreeing.

The entry was right about one placeholder and wrong about the other, and the safe-sounding one was
the wrong one: 5.5 was about 2.1 GiB high, but the code default of 2.0 was about 1.3 GiB low, so a
deployment wiring subagents without the compose file was admitting a spawn onto room the tier would
overrun.

The roster's alternate entry needed no figure of its own, since no GPU executor exists for it at
all: its `gpu_endpoint` falls back to its own CPU server, so its 2.5 charges the ledger for a
placement that always runs on the CPU.

What is not fixed is what the request means for a second spawn: the ledger charges one tier's whole
footprint per spawn, and a second spawn onto that running process allocates nothing, so refusing it
buys decode speed rather than memory. That is recorded at
[inference-model-manager.md](../index.md#inference-model-manager).

## History

- 2026-08-07: Opened by the cortex reservation measurement, which deliberately left this term alone.
- 2026-08-08: Closed by measuring the tier one day later, recorded at
  [ADR-0012 decision 14](../../adr/ADR-0012-resource-governance.md) with the procedure in
  [runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md) section 2c. Proven on the stack: under
  the old figure the live GPU branch could not select itself and the tier served no task; under 3.5
  the same command places one spawn there, answered in 152.11 ms against 13134.73 ms for the sibling
  that overflowed. The branch was shown able to fail first by pointing the GPU endpoint at a closed
  port.
- 2026-08-08: The two declarations are tied together by nothing but the comments that say so, since
  `crosscheck.py` reads module-level constants where these are a pydantic field default and a
  compose environment value.
- 2026-08-08: With this measured, every term of the VRAM budget is now a measurement rather than a
  declared figure.
