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
`_REASONING_OFF`, with the budget kept beside it and `scripts/flagcheck.py`'s requirement re-spelled
the same way; the rendering column above says the behaviour follows the spelling.

## Trail

- 2026-09-02: the per-family probe this entry asked for was drawn by the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) and is recorded above. The
  trigger is unchanged.
