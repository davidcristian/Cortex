# The subagent tier's thinking flag is deprecated on the image this repo pulls

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Trigger:** the shipped pair, `--chat-template-kwargs '{"enable_thinking": false}'` with
`--reasoning-budget 0`, no longer parses on the build `ghcr.io/ggml-org/llama.cpp:server` names,
which `:server-cuda` names too. Neither image is in the tree. To decide it, read the tag's amd64
`org.opencontainers.image.version` label from the registry, extract that image's `/app` layer, and
run its `llama-server` with the pair against a missing model file under `docker run --network none`:
it has not fired while the first error is the missing model. Today both tags name build 11434.
**Verified:** 2026-10-07

`ghcr.io/ggml-org/llama.cpp:server` prints this on every subagent boot:

```
Setting 'enable_thinking' via --chat-template-kwargs is deprecated. Use --reasoning on /
--reasoning off instead.
```

So one of the two flags each subagent server uses is on a deprecation clock. The replacement was
measured on 2026-09-02 on `b10680-d7bd3bfca`: `--reasoning off` alone renders the prompt exactly as
the kwarg does on both families, and on the E4B pick it matched the shipped pair character for
character on 40 of 40 seed-paired constrained draws. On the Qwen pick, where no row of the pair was
drawn, it wrote nothing to the reasoning channel in 20 draws and delivered 19. It is the kwarg's
own behaviour under a new name, not a third setting, so the pair does not collapse to one flag: the
budget alone loses more answers than the pair on the E4B pick and does nothing on the Qwen pick.

When the kwarg stops parsing, the change is a rename: `--reasoning off` in place of the kwarg in
both subagent compose files and in the hosted tier's `_SUBAGENT_TAIL`
(`cortex_model_manager/config.py`), with the budget kept beside it, the `Flag` pair in
`scripts/subagentflags.py` renamed the same way, and the fixtures in `test_model_roster.py`,
`test_flagcheck.py` and `test_hostedtiers.py` with it. The injection test reads the kwarg off the
tier's argv by name, so `_TEMPLATE_KWARGS_FLAG` in `test_injection_defense_live.py` and
`test_switch_rows.py` changes too, and so do the docs that name the flag: ADR-0043, ADR-0049, the
subagents-cpu and injection-probes runbooks, and the brain-inference-live module doc.

## History

- 2026-08-26: opened by the close of
  [R-456](456-a-constrained-request-loses-the-thinking-switch.md), whose live runs put the warning
  in front of a reader for the first time.
- 2026-09-02: the per-family probe this entry asked for was drawn by the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) and is recorded above. The
  trigger is unchanged.
- 2026-09-11: read against the cached image and the tree, and not fired. The stack pulls the image
  the probe ran on, `ghcr.io/ggml-org/llama.cpp:server` at `sha256:db057ec90de0`, build 10680 at
  commit `d7bd3bfca`. Started against a missing model file with the shipped pair, it printed the
  deprecation line at 5.8 ms and then failed on the model file and nothing else, so the kwarg still
  parses; with `--reasoning off` in its place it printed no warning and failed the same way. Its
  `--help` lists the successor as `-rea, --reasoning [on|off|auto]`, default `auto`.
- 2026-09-17: read against the image a fresh pull gets, and not fired. The tag now names build
  10991 at commit `930e2fa59`, created 2026-09-16, amd64 manifest `sha256:053921c63646`, while this
  machine's cache still holds build 10680, which every figure above was measured on. Build 10991,
  pulled by digest and removed afterwards, still has the same deprecation warning in
  `libllama-common.so`, still lists `--chat-template-kwargs` in `--help`, and still lists `-rea,
  --reasoning [on|off|auto]` with default `auto`; its server library still type-checks an
  `enable_thinking` value. No server was started, so this shows the warning and the flag are still
  in the build; it does not show that the flag still parses or that the tier renders the same
  prompt on 10991 as on 10680. The places a rename would touch have moved: the hosted tier's tail
  is now `_SUBAGENT_TAIL`, which since 2026-09-13 also sets `--cache-ram 0`, and the requirement is
  the `Flag` pair in `scripts/subagentflags.py`, read by `flagcheck.py` since the flag rules moved
  there on 2026-09-15.
- 2026-09-24: read against both tags, and not fired. The trigger watched only `server`, while the
  hosted tier's `_SUBAGENT_TAIL` runs on `server-cuda`, so it now names both. Both tags name build
  11146 at commit `7fe450e19`, created 2026-09-23. On that build's `server` image, read from its
  library layer without Docker, `libllama-common.so` still has the warning, `--help` still lists
  `--chat-template-kwargs` and `-rea, --reasoning [on|off|auto]`, and the server library still
  type-checks a request's `enable_thinking`. No server was started.
- 2026-10-03: read against both tags, and not fired. Both now name build 11347 at commit
  `5fc4f3c8c`, created 2026-10-02, while this machine's cache still holds build 10680. The `server`
  image's `/app` layer, run with the shipped pair against a missing model file under `docker run
  --network none` and no GPU, printed the deprecation warning first and then failed on the model
  file alone, so the kwarg still parses; with `--reasoning off` in its place it printed no warning
  and failed the same way. Its `--help` still lists `--chat-template-kwargs`, `-rea, --reasoning
  [on|off|auto]` with default `auto`, and `--reasoning-budget` with no deprecation. The trigger
  now names the check that decides it rather than the warning, which is a proxy. The rename list
  above missed the injection test's two `_TEMPLATE_KWARGS_FLAG` constants and the docs, and the
  Qwen figure was quoted as a match with the pair when no pair row was drawn on that pick.
- 2026-10-07: read against both tags, and not fired. Both now name build 11434 at commit
  `5e03bdd87`. The `:server` image, pulled by digest so the cached tags did not move and removed
  after, printed the deprecation warning and then failed on the missing model. So did
  `cortex-model-host`, rebuilt on 2026-10-06 on build 11429, which is the hosted subagent tier's
  engine.
