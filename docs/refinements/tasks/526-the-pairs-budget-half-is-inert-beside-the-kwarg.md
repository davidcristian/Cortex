# The pair's budget half is inert beside the kwarg, on both families and both builds measured

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** a llama.cpp build on which a subagent server carrying the kwarg alone writes into the
reasoning channel where the pair does not, which is the reading the budget was added on; or the
kwarg's deprecation biting, when the argv is being rewritten anyway.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-15

Opened 2026-09-02 by the close of
[R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md).

Every subagent server this repo starts carries both `--chat-template-kwargs '{"enable_thinking":
false}'` and `--reasoning-budget 0`, and `scripts/flagcheck.py` holds every one of them to that
pair, which is one of the three requirements that gate carries. The budget was added
on a reading of 2026-08-26 (the ADR-0005 thinking-lever addendum) that the kwarg alone left a 200
token trace running under a `response_format` on the E4B pick. On the two builds measured since,
`b10666` and `b10680`, the kwarg alone and the pair were identical to the character on 20 of 20
matched seeds (the marker addendum), and `--reasoning off` alone, which renders what the kwarg
renders and sets no budget, was identical to the pair on 40 of 40 (the budget-alone addendum). On
the Qwen pick the kwarg renders the thought already closed inside the prompt, where a sampler that
watches generated tokens has nothing to act on. So on current builds the second flag does nothing
beside the first on either family, and the gate holds every server to a flag with no measured
effect.

**Why it was left.** The flag is harmless where it is inert; it was measured mattering on one
earlier build, and nothing pins the build the stack pulls, since the compose files name the image by
a mutable tag; and it is the one half of the pair the engine has not deprecated. Removing it would
trade a flag that costs nothing for a re-measurement on every image bump.

**What would close it.** Nothing, unless the trigger fires. A build that reproduces the 2026-08-26
reading keeps the pair and records the build; the deprecation biting is the moment to re-read the
pair as `--reasoning off` beside the budget on both families and drop whichever half is still
inert.

## Trail

- 2026-09-02: opened by the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md), whose measurement made
  the budget's inertness beside the kwarg a reading on both families rather than on one.

- 2026-09-04: re-derived and still open, and the entry's own reading about pinning was confirmed
  exactly. No `@sha256` appears in `docker/` or in either Dockerfile: three compose files name
  `ghcr.io/ggml-org/llama.cpp:server` and `brain/Dockerfile.modelhost` builds both stages `FROM
  ghcr.io/ggml-org/llama.cpp:server-cuda`, all mutable tags, and no service sets a `pull_policy`.
  The trigger has not fired, since it asks for a build on which the kwarg alone behaves differently
  from the pair and no build past 10680 was measured. Both engine tags have moved past the cached
  images, which is the occasion to re-measure the pair rather than evidence about it; the ADR-0005
  engine-tag addendum records the digests.

- 2026-09-13: re-derived, and the second limb of the trigger nearly fired without closing anything.
  Every subagent server's argv was rewritten tonight to turn off the host-RAM prompt cache, in both
  compose overrides and the model host's hosted tier, and `scripts/flagcheck.py` gained a third
  requirement for that flag. The pair was carried through that rewrite untouched, because the limb
  names the kwarg's deprecation as the occasion to re-read the pair and the engine has not
  deprecated it yet; a rewrite for another reason is not that occasion, since it brings no new
  reading of what the budget does beside the kwarg. The first limb has not fired either: no build
  past `b10680` has been measured, and the two cached engine digests are the ones the bullet above
  read. The sentence above is corrected, the gate now requiring three things of every server rather
  than the two this entry was written against.

- 2026-09-15: re-derived and still open. Both call sites still spend the pair, the two subagent
  compose overrides writing it into each server's argv and the model host's `_SUBAGENT_TAIL`
  writing it into the hosted tier's, and `scripts/flagcheck.py`
  still holds every derived server to the pair as one of its three requirements. Both engine tags
  have moved past the cached images again: `server` is cached at `sha256:db057ec90de0` against a
  registry index of `sha256:6a8b3fbc10e6`, and `server-cuda` at `sha256:952424b09abc` against
  `sha256:e2eebf1bd901`. Re-reading the pair on the moved tags was declined tonight for this
  entry's own stated reason, that a new build's answer either way keeps the pair, so the
  measurement costs a pull and a seeded sitting of forty draws and changes no decision. The second
  limb has not fired either, the engine having still not deprecated the kwarg.
