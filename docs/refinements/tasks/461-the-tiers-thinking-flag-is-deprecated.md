# The subagent tier's thinking flag is deprecated on the image this repo pulls

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Trigger:** a llama.cpp image whose `--chat-template-kwargs` no longer parses, or a subagent
server that fails to start after an image bump; either arrives as a tier that will not come up.

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

**What would close it.** One probe per lineup family against a server started with `--reasoning off`
alone, on the constrained request shape, reading whether the trace is gone. If it is, the pair
becomes one flag in all three files; if it is not, the record says which flag each family needs and
why both stay.
