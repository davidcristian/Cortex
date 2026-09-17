# The subagent tier's thinking flag is deprecated on the image this repo pulls

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Trigger:** a llama.cpp image whose `--chat-template-kwargs` no longer parses, or a subagent
server that fails to start after an image bump; either arrives as a tier that will not come up.
The compose files name the floating tag `ghcr.io/ggml-org/llama.cpp:server`, so the image is not
in the tree: read the digest `docker buildx imagetools inspect` names for that tag, and on that
image check that `strings` over `/app/libllama-common.so*` still carries the deprecation warning
quoted below and that `--help` still lists `--chat-template-kwargs`, without starting a server.
**Verified:** 2026-09-17

Opened 2026-08-26 by the close of
[R-456](456-a-constrained-request-loses-the-thinking-lever.md), whose live runs put the warning in
front of a reader for the first time.

`ghcr.io/ggml-org/llama.cpp:server` prints this on every subagent boot:

```
Setting 'enable_thinking' via --chat-template-kwargs is deprecated. Use --reasoning on /
--reasoning off instead.
```

So one of the two flags each subagent server now carries is on a deprecation clock, and the
replacement it names is untested here. `--reasoning off` may well do what both current flags do
together, in which case the pair collapses to one flag and the entry beside this one about holding
three spellings together gets smaller with it.

**Why it was left.** The image still accepts the flag, and a deprecation warning is not a failure.
Swapping a working lever for an untested one on the same day the working one was measured would
have put an unmeasured flag in the place of the measured one, which is the shape of the defect this
whole run exists to fix.

**The probe was drawn, and the pair does not collapse.** Measured 2026-09-02 on `b10680-d7bd3bfca`
(ADR-0005 budget-alone addendum): `--reasoning off` alone renders the prompt exactly as the kwarg
does on both families, the E4B prompt without its `<|think|>` and the Qwen prompt with its thought
closed, and on the E4B pick it was identical to the shipped pair to the character on 40 of 40
seed-paired constrained draws, traces and marker fragments included; on the Qwen pick it delivered
19 of 20. It is the kwarg's own behaviour under a new spelling and not a third lever. The other
half of the pair cannot stand alone either: the budget by itself loses more answers than the pair
on the E4B pick and does nothing on the Qwen pick, which is why the pair stays.

**What would close it.** The trigger firing. When the kwarg stops parsing, the change is a spelling
swap, `--reasoning off` in place of the kwarg on both compose servers and in the hosted tier's
`_SUBAGENT_TAIL` (`cortex_model_manager/config.py`), with the budget kept beside it, the `Flag` pair
in `scripts/subagentflags.py` re-spelled the same way, and the fixtures that spell the pair in
`test_model_roster.py`, `test_flagcheck.py` and `test_hostedtiers.py` with it; the rendering column
above says the behaviour follows the spelling.

## Trail

- 2026-09-02: the per-family probe this entry asked for was drawn by the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) and is recorded above. The
  trigger is unchanged.
- 2026-09-11: read against the cached image and the tree, and not fired. The image the stack
  pulls is the one the probe above ran on, `ghcr.io/ggml-org/llama.cpp:server` at
  `sha256:db057ec90de0`, reporting build 10680 at commit `d7bd3bfca`. Started against a missing
  model file with the shipped pair, it printed the deprecation line quoted above at 5.8 ms and
  then failed on the model file and nothing else, so the kwarg still parses; started with
  `--reasoning off` in the kwarg's place it printed no warning and failed the same way. Its
  `--help` lists the successor as `-rea, --reasoning [on|off|auto]`, default `auto`. The pair
  is still on both compose servers, in `docker/docker-compose.subagents.yml` and
  `docker/docker-compose.subagents-roster.yml`, still the hosted tier's `_REASONING_OFF` in
  `cortex_model_manager/config.py`, and still what `scripts/flagcheck.py` requires at lines 94
  and 95.
- 2026-09-17: read against the image a fresh pull gets and the tree, and not fired. The tag has
  moved since the bullet above: `ghcr.io/ggml-org/llama.cpp:server` now names build 10991 at commit
  `930e2fa59`, created 2026-09-16, whose amd64 manifest is `sha256:053921c63646`, while this
  machine's cache still holds build 10680, the one every figure above was measured on. That image,
  pulled by digest and removed afterwards, still carries the same deprecation warning in
  `libllama-common.so`, still lists `--chat-template-kwargs` in `--help`, and still lists `-rea,
  --reasoning [on|off|auto]` with default `auto`; its server library still type-checks an
  `enable_thinking` value. No server was started, so this reading shows that both the warning and
  the flag are still in the build; it does not show that the flag still parses, nor that the tier
  renders the same prompt on build 10991 as on build 10680. The places the swap would touch have
  moved: the hosted tier's tail is now `_SUBAGENT_TAIL`, which since 2026-09-13 also carries
  `--cache-ram 0`, and the gate's requirement is the `Flag` pair at lines 81 and 82 of
  `scripts/subagentflags.py`, which `flagcheck.py` reads since the flag rules moved there on
  2026-09-15; the remedy above now names them.
