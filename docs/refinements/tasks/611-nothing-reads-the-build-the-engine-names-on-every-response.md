# Nothing reads the build the engine names on every response

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-08 by the close of
[R-299](299-prose-cites-an-engine-build-nothing-pins.md), which repaired five citations by hand and
found the field that would have made repairing them unnecessary.

llama-server names its own build on everything it answers. Every chunk of a stream and every
non-streaming completion carries `system_fingerprint`, and `/props` reports the same string as
`build_info`. Measured 2026-09-08 on `ghcr.io/ggml-org/llama.cpp:server`, the shipped subagent pick
at `-ngl 0`: both read `b10680-d7bd3bfca`, and all seven chunks of one streamed completion carried
the field. That is the same spelling the corpus already quotes, `b10298-15586e2d7`, which was itself
read off `system_fingerprint` on 2026-08-08 rather than off any `--version`.

Nothing in this tree reads either. `system_fingerprint` appears in no Python, Rust or Markdown file
here, `decode.py` reads `timings` and `choices` off a chunk and drops the rest, and `/props` is
asked for nothing. So every figure this stack produces is attributed to a build by hand, in prose,
by whoever was watching, and a figure whose sentence is not updated goes on naming a build that has
not run here for weeks. Five such sentences were repaired on the day this was filed, and the repair
is a claim about the past that the next reader cannot check.

**Why this is not the tag question.** Pinning `ghcr.io/ggml-org/llama.cpp:server` and
`:server-cuda` by digest decides which build runs, which is a deployment choice and is deliberately
left open (ADR-0005 build-provenance addendum). Reading the fingerprint decides whether a
measurement says which build produced it, and is true whether or not anything is pinned. The two
are independent, and this is the half that does not change what the stack starts.

**What would close it.** Somewhere the brain already talks to the engine at boot: the trace lever
probe asks one model-free question per endpoint and logs its answer. A build reading belongs beside
it, either as a second field on that line or as a `/props` read of its own, so a stack says in its
own log which engine each endpoint is running before anything is measured against it. A port arm on
`InferenceEvent` is the larger alternative and reaches per-completion provenance, which the log line
does not; it is a contract change, so it needs the fake, the contract test and the seam's own
wording, and this entry does not choose between them. Either way a runbook stops asking an operator
to remember which build they were on.

## Trail

- 2026-09-08: opened by the close of
  [R-299](299-prose-cites-an-engine-build-nothing-pins.md), recorded in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) build-provenance addendum, which measured the
  two fields above and repaired the five prose citations that this would have made unnecessary.
