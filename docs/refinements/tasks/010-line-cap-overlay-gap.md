# The line cap's missing overlay coverage

**Status:** landed 2026-08-03
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Found 2026-08-03 while reviewing a landed change, and recorded here because a gate that cannot
fail is a defect in its own right, whatever it happens to have missed. `scripts/linecap.py` held
`SOURCE_SUFFIXES = {".py", ".rs"}` from the day it was written, which was correct then:
[ADR-0001](../../adr/ADR-0001-architecture.md) open question 6 scoped both the coverage gate and the
300-line cap to `.py`/`.rs` while the overlay was "kept minimal". ADR-0011's 2026-07-01 addendum
reversed that for coverage and said so; nothing reversed it for the cap, and nothing noticed,
because the gate kept passing. **How long, and what it let through:** thirty-three days from the
overlay's first gated component to 2026-08-03, over a tree that reached 107 TypeScript files, 65
of them the non-test sources the cap would have been measuring the whole time.
Two entries in [body-overlay.md](../index.md#body-overlay) tracked cap violations by eye over that window
and both drifted. `bridge/demoBridge.ts` was recorded at 326 on the day it already stood at 351,
and it was still 351 fourteen days later; `overlay/panelPlacement.ts` crossed the cap the day
after the entry that called demoBridge the only one over it, reached 371, and sat there for
thirteen days until an unrelated ResizeObserver change took it to 295 by accident. Neither the
false claim nor the stale number cost anything beyond themselves, which is the point: the failure
of an unenforced rule is silent by construction, and it was found by a review rather than by a
gate. **Landed the day it was found**, so this entry is a record rather than a deferral: the scan
now covers `.ts`/`.tsx`, `demoBridge.ts` was split rather than exempted, and the whole decision
including what stays outside the cap is in the ADR-0011 line-cap addendum. Proven able to fail
before being trusted, planted file by planted file, per the same distrust-green rule that turned
this up.

## Trail

- 2026-08-03: Found while reviewing a landed change and landed the same day, so the entry is a
  record rather than a deferral. `scripts/linecap.py` had scanned `.py` and `.rs` only since it
  was written, right while ADR-0001's open question 6 scoped the cap away from a frontend kept
  minimal and wrong from ADR-0011's 2026-07-01 addendum onward, so for thirty-three days AGENTS.md
  gate 1 stated a rule over a 65-module tree that nothing measured. The cap now covers
  `.ts`/`.tsx` with Vitest's own notion of a test file as its exclusion, and `demoBridge.ts` was
  split rather than exempted, which decremented body and overlay. What it made visible increments
  this area, and the index records the proto as the other thing outside the cap, a decision rather
  than a deferral, since capping it would conflict with the invariant that the seam is defined
  once. The index measured `proto/body.proto` at 314 lines when it recorded that decision.
