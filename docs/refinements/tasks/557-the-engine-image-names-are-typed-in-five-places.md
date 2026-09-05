# The engine image names are typed in five places

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a compose file or the model-host Dockerfile naming a different engine image or tag
than the one it names today, which is the retag the ADR-0005 engine-tag addendum says is one
`docker compose pull` away; or a second harness starting its own server from a typed image name.

Opened 2026-09-05 by the close of
[R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which typed the
CPU engine image into the injection harness beside the CUDA one already there.

`_GPU_IMAGE` and `_CPU_IMAGE` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
spell `ghcr.io/ggml-org/llama.cpp:server-cuda` and `ghcr.io/ggml-org/llama.cpp:server`. The three
compose files that start CPU servers spell the second, `brain/Dockerfile.modelhost` builds both its
stages from the first, and `test_unfenced_correction_live.py` types the first again. No registry row
in `scripts/crosscheck.py` holds any of them equal: the harness reads the tier's flags off the
sidecar precisely so that a retuned tier moves its rows, and the image those flags are handed to is
the one thing about the server it still remembers on its own.

**Why it was left.** An image name is not a value any Python module declares, so the registry has
no `Site` to anchor it to without electing one of the test files as the declaration, and the tag is
mutable anyway: the engine-tag addendum records that both tags already resolve to builds newer than
the cached ones, so equality of the spelling says nothing about equality of the build. The close
typed the second name in the shape the first already had rather than build a coupling for a value
whose sameness is not the property that matters.

**What would close it.** Either a `Site` on the harness's two constants with the compose and
Dockerfile spellings as mentions, accepting a test file as a declaration the way
`fixturecouplings.py` already does; or a digest pin on the stack, at which point the pin is the
declaration and the harness reads it.

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which added
  the CPU image's spelling to the harness.
