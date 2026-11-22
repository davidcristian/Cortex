# The NVFP4 file's first request is drawn only on a new container's first load

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-22

[R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md) compares
the two Qwen files on a handoff's first token, by twelve loads of 2026-11-22
([readings](../../readings/nvfp4-deep-pair.md#the-deep-turn-of-a-handoff)). Each of those loads
was the first deep load of a new model host container, which is the first handoff after a stack
start. There the NVFP4 file's first request has 2.03 times the Q4 file's fixed time, and its
first token comes 1.76 times as late at 896 prompt tokens.

Rows of the same date on the Q4 file alone say that 0.90 of its fixed time is the card's
library compiling kernels, which a container pays once
([readings](../../readings/deep-first-request.md)). A later load in the same container has
0.10 of it. The NVFP4 file has no such row, so two things are not known:

- Whether the NVFP4 file's larger fixed time is the same compile.
- What a later handoff of one stack gets. If the NVFP4 file's fixed time also falls to a
  tenth, its prompt pass at 1.46 to 1.76 times the Q4 file's rate reaches every handoff but
  the first, and the comparison R-1244 has holds for the first handoff of a stack only.

What would close it: both files in turn inside one model host container, three later loads a
file at 896 and at 10,856 prompt tokens, with each file's first load in that container read
apart. `nvfp4-probes/firstfixed.py` under `measurements/model-baseline-2026-11-16/` draws
such loads and names the Q4 file only today. The whole deep turn of a later handoff then
follows as in the pair record.

## History

- 2026-11-22: filed by the Q4 file's rows on its first request after a load
  ([R-1291](1291-a-new-model-host-container-compiles-the-cards-kernels-again.md)), which
  showed that every load of the pair record was a new container's first.
