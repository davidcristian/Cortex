# The pair's budget half has no effect beside the kwarg, on both families and both builds measured

**Status:** open, waiting for its trigger
**Area:** inference
**Trigger:** a row in the thinking-switch readings, on a llama.cpp build past `b10680`, in which a
subagent server using the kwarg alone writes into the reasoning channel where the pair does not,
which is the reading the budget was added on; or the kwarg's deprecation taking effect, which
R-461 watches, when the argv is being rewritten anyway.
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-09-24

Every subagent server this repo starts uses both `--chat-template-kwargs '{"enable_thinking":
false}'` and `--reasoning-budget 0`, and `scripts/flagcheck.py` requires the pair on every one of
them. The budget was added on a reading of 2026-08-26 (ADR-0049) that the kwarg alone left a
200-token trace running under a `response_format` on the E4B pick. On the two builds measured since,
`b10666` and `b10680`, the kwarg alone and the pair were identical character for character on 20 of
20 matched seeds, and `--reasoning off` alone, which renders what the kwarg renders and sets no
budget, was identical to the pair on 40 of 40 (both in the thinking-switch readings). On the Qwen
pick the kwarg renders the thought already closed inside the prompt, where a sampler watching
generated tokens has nothing to act on. So on current builds the second flag does nothing beside the
first on either family.

The flag is harmless where it has no effect; it was measured mattering on one earlier build, and
nothing fixes the build the stack pulls, since the compose files name the image by a mutable tag;
and it is the one half of the pair the engine has not deprecated. Removing it would trade a flag
that costs nothing for a re-measurement on every image bump.

## History

- 2026-09-02: opened by the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md), whose measurement made the
  budget's lack of effect beside the kwarg a reading on both families rather than on one.
- 2026-09-04: checked again and still open, and the entry's own reading about fixed digests was
  confirmed. No `@sha256` appears in `docker/` or in either Dockerfile: three compose files name
  `ghcr.io/ggml-org/llama.cpp:server` and `brain/Dockerfile.modelhost` builds both stages `FROM
  ghcr.io/ggml-org/llama.cpp:server-cuda`, all mutable tags, and no service sets a `pull_policy`.
  The trigger has not fired, since no build past 10680 was measured.
- 2026-09-13: checked again, and the second clause of the trigger nearly fired without closing
  anything. Every subagent server's argv was rewritten to turn off the host-RAM prompt cache, in
  both compose overrides and the model host's hosted tier, and `scripts/flagcheck.py` gained a third
  requirement for that flag. The pair went through that rewrite untouched, because the clause names
  the kwarg's deprecation as the occasion to re-read the pair and the engine has not deprecated it
  yet. The first clause has not fired either: no build past `b10680` has been measured.
- 2026-09-15: checked again and still open. Both call sites still use the pair, the two subagent
  compose overrides writing it into each server's argv and the model host's `_SUBAGENT_TAIL` writing
  it into the hosted tier's, and `scripts/flagcheck.py` still requires it of every derived server.
  Both engine tags have moved past the cached images again: `server` is cached at
  `sha256:db057ec90de0` against a registry index of `sha256:6a8b3fbc10e6`, and `server-cuda` at
  `sha256:952424b09abc` against `sha256:e2eebf1bd901`. Re-reading the pair on the moved tags was
  declined for this entry's own stated reason, that a new build's answer either way keeps the pair,
  so the measurement costs a pull and a seeded run of forty draws and changes no decision.
- 2026-09-24: checked again and not fired. The thinking-switch readings still hold no build past
  `b10680`, and the trigger now names that record, since a build's behaviour reaches this tree only
  as a row there. Both engine tags now name build 11146, which still lists the kwarg with its
  deprecation warning and deprecates nothing about `--reasoning-budget`
  ([R-461](461-the-tiers-thinking-flag-is-deprecated.md)). The inference adapter now logs the build
  each model's server names, which shows a tier's image bump and measures nothing.
