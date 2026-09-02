# The rendering column is one build's sweep, and an engine bump reopens every row of it

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** an engine bump under this stack, meaning the `server-cuda` or `server` digest pinned
by the gpu override's model-host base image or by the subagents override moving to a new llama.cpp
build, since the column is a property of one build's chat handlers and a handler that started
gating its reasoning rule on `enable_thinking` would break it with nothing reporting the break.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-02 by the close of
[R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), which read every row of the
lineup section's rendering column back through `just switch-tail` on `b10680-d7bd3bfca`.

Every row of that column now stands on a sample the reader published, and every one of them was
drawn on one build. The rule the column carries, that a template rendering the thought already
closed holds the switch under a `response_format` and one leaving it open does not, is a reading
of that build's handlers rather than a theorem, which is what the reader exists to say the day it
stops being true. Nothing in the tree runs the sweep that would say so. The sitting that read the
nine rows was a scratch shell loop: start a pinned llama-server on one pick off the mount with
neither reasoning flag, wait on `/health`, run the probe with `CORTEX_THINKING_MODEL` naming the
pick and `CORTEX_THINKING_REPEATS=5`, stop the server, publish the sample, and move to the next
pick. It served nine picks in about 26 minutes on the 24 GB card, the three rows the lineup
section places at `-ngl 0` among them, after the CPU image had decoded the E2B at under two tokens
a second on the night; it is recorded nowhere but in the addendum that used it.

**Why it was left.** The sweep is a sitting and not a gate: it needs the card, the mount and
about an hour, and the rule it re-reads carries no shipped behaviour, since every bound that pairs
a cap with the switch also sends `trace_tokens=0` where the engine reads it. A committed driver
that serves eleven picks one at a time is a recipe with a lifecycle of its own, and it was not
worth writing against a build that had just been read.

**What would close it, when it bites.** Re-run the lineup on the new build and publish every row
through `just switch-tail`, then rewrite the column where a row moved. The cheaper half is a
`just switch-lineup` recipe holding the loop above, so the next bump re-reads the column in one
command rather than from a scratch file; the model-host sidecar already knows how to start and
stop one llama-server per tier, and is the obvious thing to drive it with. The three rows the
lineup section places at `-ngl 0` are owed that placement in the re-run, since the sitting that
opened this read them on the card.

## Trail

- 2026-09-02: opened by the close of
  [R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), whose ADR-0005 lineup-tails
  addendum records the sweep and the build it read.

- 2026-09-02: the sample the sweep publishes now names the engine build and the model file the
  server reported on `GET /props`, by the close of
  [R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md), so the
  next sweep copies the record's artifact and build columns off each report rather than off the
  loop's notes.
