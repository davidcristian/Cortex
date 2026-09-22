# The subagent tier's thinking flag is deprecated on the image this repo pulls

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Trigger:** a llama.cpp image whose `--chat-template-kwargs` no longer parses, or a subagent
server that fails to start after an image bump; either arrives as a tier that will not come up.
The compose files name the floating tag `ghcr.io/ggml-org/llama.cpp:server`, so the image is not
in the tree: read the digest `docker buildx imagetools inspect` names for that tag, and on that
image check that `strings` over `/app/libllama-common.so*` still contains the deprecation warning
quoted below and that `--help` still lists `--chat-template-kwargs`, without starting a server.
**Verified:** 2026-09-17

`ghcr.io/ggml-org/llama.cpp:server` prints this on every subagent boot:

```
Setting 'enable_thinking' via --chat-template-kwargs is deprecated. Use --reasoning on /
--reasoning off instead.
```

So one of the two flags each subagent server uses is on a deprecation clock. The replacement was
measured on 2026-09-02 on `b10680-d7bd3bfca`: `--reasoning off` alone renders the prompt exactly as
the kwarg does on both families, and on the E4B pick it matched the shipped pair character for
character on 40 of 40 seed-paired constrained draws, 19 of 20 on the Qwen pick. It is the kwarg's
own behaviour under a new name, not a third setting, so the pair does not collapse to one flag: the
budget alone loses more answers than the pair on the E4B pick and does nothing on the Qwen pick.

When the kwarg stops parsing, the change is a rename: `--reasoning off` in place of the kwarg on
both compose servers and in the hosted tier's `_SUBAGENT_TAIL` (`cortex_model_manager/config.py`),
with the budget kept beside it, the `Flag` pair in `scripts/subagentflags.py` renamed the same way,
and the fixtures in `test_model_roster.py`, `test_flagcheck.py` and `test_hostedtiers.py` with it.

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
