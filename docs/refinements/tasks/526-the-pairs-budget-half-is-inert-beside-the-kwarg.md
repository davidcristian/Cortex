# The pair's budget half is inert beside the kwarg, on both families and both builds measured

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** a llama.cpp build on which a subagent server carrying the kwarg alone writes into the
reasoning channel where the pair does not, which is the reading the budget was added on; or the
kwarg's deprecation biting, when the argv is being rewritten anyway.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-02 by the close of
[R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md).

Every subagent server this repo starts carries both `--chat-template-kwargs '{"enable_thinking":
false}'` and `--reasoning-budget 0`, and `scripts/flagcheck.py` requires both. The budget was added
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
