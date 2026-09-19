# ADR-0059: The engine's prompt cache, sized per tier

**Status:** Accepted (2026-09-13)

## Context

`llama-server` keeps a prompt cache in host RAM for a conversation whose server slot has been taken,
so a returning conversation is restored rather than evaluated again. The flag that sizes it is
`--cache-ram`, and on the build this stack pulls (`b10680-d7bd3bfca`) its default is 8192 MiB per
server. No compose file and no model-host argv passed the flag, so every server took that default.

8192 MiB is the whole `mem_limit` the subagent compose file puts on each CPU server, and a third of
the 24 GiB cap the model host's tiers share. Every server here reads its weights through a memory
map inside the same cgroup as its cache, so a cache that grows makes the kernel reclaim the mapped
model file the server reads on every token. A CPU subagent server sits at about nine tenths of its
cap once loaded, before its first request. Where the weights are on the card nothing in the page
cache replaces them, and the kernel kills the process instead: a `Qwen3.5-4B` server at `-ngl 99`
under the 8 GiB cap was killed with an `oom` event 174 seconds into a measurement run. The
measurements are in [prompt cache](../readings/prompt-cache.md).

## Decision

1. **Every tier states its own `--cache-ram`, and none takes the engine's default.** The number a
   tier was measured at is the number it runs with, and an engine that changes its default cannot
   change a tier's memory ceiling. The value is per tier and is not a deployment setting.

2. **Every subagent server runs `--cache-ram 0`.** That covers the two CPU compose servers
   (`docker/docker-compose.subagents.yml` and `docker/docker-compose.subagents-roster.yml`) and the
   model host's GPU-placed subagent tier, whose tail `_SUBAGENT_TAIL` in
   `brain/packages/model_manager/src/cortex_model_manager/config.py` includes it. A CPU container
   has under a tenth of its cap to give a cache, and the tier's subtasks are one-shot, sharing no
   prefix: over twelve distinct prompts the flag cost nothing measurable. On a rotating conversation
   shape a returning request takes about twice as long without it, which is still a small fraction
   of a second, against up to 8 GiB of a cap shared with another tier's weights.
   `scripts/flagcheck.py` checks the flag as one of the requirements every subagent server must have
   in both placements ([ADR-0043](ADR-0043-subagent-server-flags.md)), so a server a later override
   adds is covered.

3. **The cortex keeps 8192 MiB.** It is the tier a cache pays off on: its conversations are long and
   returned to. A cached conversation of about 4000 prompt tokens costs about 1.3 GiB, every return
   was restored at about half the time of a cold prompt evaluation, and nothing was paid up front.
   8192 MiB is one conversation at the tier's full context, and a smaller ceiling would exclude the
   longest conversations, which are the ones a user waits through. Beside the GPU subagent tier,
   which loads with no cache of its own, the pair's worst case stays under the model host's cap. It
   is `_CORTEX_PROMPT_CACHE` in `config.py`.

4. **The deep tier runs `--cache-ram 0`.** A deep conversation costs about 3.5 GiB of cache, so the
   default ceiling holds two, and the conversation coming back is the one dropped to make room: no
   request in the measured run was restored. What turning the cache off bought instead was 7.1 GiB
   of the cap and the reclamation of mapped weights, with the cgroup's peak at its cap exactly. Zero
   costs nothing on this shape and makes each request about an eighth faster.

5. **`scripts/flagcheck.py` is not extended to the cortex and the deep tier.** Its subject is what a
   subagent server must have in both of its placements; these two are per-tier values that one
   module writes once, as `_CORTEX_PROMPT_CACHE` and `_NO_PROMPT_CACHE`.

## Consequences

- The model host's roster tests assert the pair at the end of each tier's argv: `8192` on the
  cortex, `0` on the deep and GPU subagent tiers. The two compose servers write `0`, which
  `flagcheck` compares.
- The cache changes what a request costs and not what it answers: the subagent and deep runs
  returned the same completion on every seeded cell. The cortex runs agreed on ten of twelve, and
  since one prompt drew different traces between rounds within each run, that pair does not separate
  the flag from the engine's own rule that a seed reproduces a completion only against the same
  prompt-cache state ([ADR-0050](ADR-0050-live-probe-records.md) decision 8).
- `--cache-ram` governs the cache of a conversation whose slot was taken, not the prefix reuse a
  request gets when it extends the prompt its slot just answered, so a deep-tier prompt rate is not
  a cold reading because the cache is off
  ([R-110](../refinements/tasks/110-prefill-second-witness.md)).
- A new tier added to the model host states its own size in `config.py` beside the others.

## Alternatives rejected

- **A size rather than zero on the subagent servers**: the CPU containers have no headroom to give
  one, and the one-shot shape never reads a cached conversation back.
- **Leaving the cortex and the deep tier on the engine default**: it is the right number for the
  cortex today, but a default the engine can move is not a ceiling this repo measured.
- **A deployment setting for the size**: the value follows from a tier's measured shape and its
  share of one cgroup, which an operator setting cannot see.

## Related

- [ADR-0043](ADR-0043-subagent-server-flags.md) (the flags a subagent server must have),
  [ADR-0053](ADR-0053-model-host-supervisor.md) (the model host and its tiers),
  [ADR-0028](ADR-0028-grammar-constrained-subagents.md) (the measurement run whose server was
  killed).
- Module: [brain-model-manager](../modules/brain-model-manager.md).
- Readings: [prompt cache](../readings/prompt-cache.md).
