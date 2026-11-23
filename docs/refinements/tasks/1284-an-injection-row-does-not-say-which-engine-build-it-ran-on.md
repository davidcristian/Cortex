# An injection row does not say which engine build it ran on

**Status:** done 2026-11-23
**Area:** untrusted-content
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)

A row of `brain/packages/inference/tests/test_injection_defense_live.py` starts its server from the
`ghcr.io/ggml-org/llama.cpp:server-cuda` tag (`_GPU_IMAGE`). The model host is an image built from
that tag earlier, so one machine can run the two on different engine builds. On the machine the
rows of 2026-11-21 were drawn on, the tag's `llama-server --version` prints build 12169 and the
model host's `/props` reports build 12375. A row prints no build, so a count cannot be matched to
the engine that produced it. The
[injection text rows](../../readings/injection-text-rows.md) of 2026-11-21 were drawn on a deep
server the model host started.

## Proposal

- Print the engine build at the start of a row. `/props` reports it as `build_info`.
- Decide whether a card row starts from the model host's image, so that a row and the stack run
  one build, or stays on the tag and names the build in its readings.

**What closes it.** A row that prints its build, and the choice of image written into ADR-0060.

## History

- 2026-11-21: filed by the injection rows at the shipped configuration
  ([R-1267](1267-qwen38-27bs-injection-row-was-drawn-at-8192-on-an-earlier-build.md)).
- 2026-11-23: Closed. `_server` prints the build its server names on `GET /props` through
  `served_build_sync` in `tests/served_build.py` once the server is healthy, before the row's
  first card reading. The card rows stay on the tag, and ADR-0060 decision 5 says why and that a
  reading names the printed build. No row was drawn for the close.
