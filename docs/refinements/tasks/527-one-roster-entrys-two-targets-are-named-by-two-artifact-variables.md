# One roster entry's two placement targets are named by two artifact variables nothing compares

**Status:** open, waiting for its trigger
**Area:** subagents
**Trigger:** a deployment that names different files in `CORTEX_MODEL_FILE_SUBAGENT` and
`CORTEX_MODEL_FILE_SUBAGENT_GPU`, whether found by a GPU-placed and an overflowed spawn of the
default entry answering differently or by reading the two variables side by side; or the hosted
subagent tier gaining a second pick, at which point the pairing has to be written down anyway. Both
halves are countable inside the repo: list every place the tree names either variable with a file
and compare the strings, reading each mention of either variable with the line after it, since a
runbook sentence can wrap the variable and its file onto two lines; and count the tiers
`ModelHostConfig().tiers()` declares, with every file variable named, whose artifact field is
aliased to a `CORTEX_MODEL_FILE_SUBAGENT` variable. Neither half reads a host's shell or `.env`,
where a deployment would really write the second file.
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Verified:** 2026-09-24

`_entry_profile` in `cortex_orchestrator.subagent_builders` gives the default entry two backends,
one per `PlacementTarget`, over `CORTEX_SUBAGENTS_GPU_ENDPOINT` and `CORTEX_SUBAGENTS_ENDPOINT`.
With the hosted tier opted in, those are two different servers whose weights are named by two
different variables: `CORTEX_MODEL_FILE_SUBAGENT` in the `command:` of
`docker/docker-compose.subagents.yml` and `CORTEX_MODEL_FILE_SUBAGENT_GPU` in the model host's env.
The second defaults to empty because the tier is opt-in, so no compose default connects them, and
section 3 of `docs/runbooks/subagents-validation.md` sets them equal by hand.
`VramBudgetPlacer.place` then picks the target by headroom, which
[ADR-0012](../../adr/ADR-0012-resource-governance.md) designed as a decision about resources and
nothing else, and [ADR-0017](../../adr/ADR-0017-subagent-model-safety.md) sends every tainted
spawn to the default entry on the premise that it is the injection-resistant pick. A deployment naming two files breaks
that premise on the GPU side only: which weights read untrusted content depends on how much VRAM was
free at the moment of the spawn.

Two ways to close it. A brain-side read of `GET /props` on both of an entry's targets, compared with
each other and never with a declared expectation, taken when both are up, with a disagreement logged
as a warning naming both paths. Or a supervisor-side declaration: the model host's tier could read
the same variable the CPU server uses, `CORTEX_MODEL_FILE_SUBAGENT`, with the `_GPU` name kept as an
override, so the shipped wiring names one artifact twice; that costs the tier's present opt-in
reading, under which an empty file means no tier. Either way the answer is compared and never
stored.

## History

- 2026-09-02: opened by the close of
  [R-508](508-a-roster-entry-names-an-endpoint-and-not-a-model.md), whose decline found this to be
  the one expectation a `/props` read could be compared with without a config setting.
- 2026-09-04: checked again and still open. The tree names either variable with a file in three
  places and all three write
  `google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf`: the substitution default in
  `docker/docker-compose.subagents.yml`, the `docker compose up` line of
  `docs/runbooks/subagents-cpu.md` section 2c, and the VRAM procedure in
  `docs/runbooks/llamacpp-gpu.md`. There is no `.env` in the checkout, and `subagent_gpu_file` still
  defaults to the empty string. `_entry_profile` still builds one entry two backends over two
  endpoints, and nothing in `scripts/` compares the three copies.
- 2026-09-11: checked again and still open. The same three places, all still writing the same file,
  at line 116 of `docker/docker-compose.subagents.yml`, line 393 of
  `docs/runbooks/subagents-cpu.md` and line 1214 of `docs/runbooks/llamacpp-gpu.md`. The tier count
  in the bullet above reads more than the shipped wiring declares: `ModelHostConfig().tiers()`
  declares one tier at the shipped default, the cortex, because the brain and subagent tiers are
  opt-in behind an empty file name, and three once both files are named. The compose config rendered
  over the base, subagents and roster files still points `CORTEX_SUBAGENTS_ENDPOINT` and
  `CORTEX_SUBAGENTS_GPU_ENDPOINT` at `http://llama-subagent:8082`, and the two modules under
  `scripts/` that name the variable, `subagentservers.py` and `hostedtiers.py`, read its prefix and
  compare no two copies of it.
- 2026-09-17: checked again and still open, but the count in the two bullets above was one place
  short. The tree names either variable with a file in four places, not three, and all four write
  `google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf`: line 126 of
  `docker/docker-compose.subagents.yml`, lines 22 and 23 of `docs/runbooks/subagents-cpu.md`, which
  give `CORTEX_MODEL_FILE_SUBAGENT` its default in a sentence written on 2026-07-01 and 2026-07-03
  and wrapped across the two lines, so a search for both on one line does not find it, line 450 of
  the same runbook in section 2c, and line 1413 of `docs/runbooks/llamacpp-gpu.md`. There is still
  no `.env`, and `subagent_gpu_file` still defaults to `""`. `ModelHostConfig().tiers()`, run from a
  scratch script, declares one tier at the shipped defaults and three with the subagent and brain
  files both named, and `subagent_gpu_file` is still the only field in
  `cortex_model_manager/config.py` aliased to a `CORTEX_MODEL_FILE_SUBAGENT` variable. The settings
  scan added the same day compares each settings field with some compose file that names it, and
  compares no two values.
- 2026-09-24: checked again and not fired, and the tree now names either variable with a file in
  three places, not four. The runbook split of 2026-09-19 moved the section 2c procedure into
  section 3 of `docs/runbooks/subagents-validation.md` and left `docs/runbooks/llamacpp-gpu.md`
  naming `CORTEX_MODEL_FILE_SUBAGENT_GPU` without a file, so the body's pointer moved with it. The
  three are line 46 of `docker/docker-compose.subagents.yml`, lines 24 and 25 of
  `docs/runbooks/subagents-cpu.md` (the wrapped sentence) and line 51 of
  `docs/runbooks/subagents-validation.md`, and all three write
  `google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf`. There is no `.env`,
  `subagent_gpu_file` still defaults to `""` and is the only field aliased to a
  `CORTEX_MODEL_FILE_SUBAGENT` variable, and `ModelHostConfig().tiers()` declares one tier at the
  shipped defaults and three with the subagent and brain files named. The deep tier's drafter,
  added on 2026-09-19 under `CORTEX_MODEL_FILE_BRAIN_DRAFT`, adds flags to the deep tier and no tier.
