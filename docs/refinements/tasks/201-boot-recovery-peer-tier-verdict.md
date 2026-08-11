# Boot recovery blaming a peer tier on the cortex

**Status:** landed 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Boot recovery still calls a peer tier's failure the cortex being gone.
Opened 2026-08-09 by the same close, which refuses that conflation everywhere else and left this
one site alone. `converge_residency` starts every `evict_models` tier inside the same `try` that
decides whether the cortex was observed serving, so one peer that will not start makes the whole
convergence answer `False`, the composition root publishes `RESIDENCY_BOOT_FAILED`, and the
overlay goes amber with "the usual assistant did not come up at startup" over a cortex that is
serving turns perfectly well. The fix is the same record threaded through that function and
through `BootWatch._converge`, with the peers no longer deciding the cortex's verdict. It was
left out because those two call sites reach the record through the manager, which sits one line
under the file cap, so the change is a split rather than an argument; and because the retry
clears the placer half within a pass either way, leaving only the readiness lie. The trigger is
a boot observed reporting that lie, which needs a deployment that both evicts a tier and has one
that will not start.
**It landed 2026-08-09, hours later and ahead of that trigger, recorded at the
[ADR-0030 boot-verdict addendum](../../adr/ADR-0030-brain-handoff.md).** `converge_residency` now
answers about the cortex and nothing else: each `evict_models` peer is cleared best effort and
restarted best effort through the swap back's own `restart_evicted`, so a `status` or a `start`
the host refuses is recorded in the manager's `StandingTiers` and skipped, while the verdict
stays what was observed of the cortex. Three things about it, two of them corrections to this
entry's own text.
**The blocker was still the real one**, to the line: `residency.py` stood at 299 of 300 and both
call sites reach the record through it. The split is by responsibility rather than by count:
`ResidencyBoard` (`residency_board.py`) now owns the bookkeeping the moves and the restore both
publish into (which model the GPU serves, what a human is told, whether a scope owns the card,
and the one condition all three are written and waited on under), leaving the manager *when* the
GPU may change hands and *who may lease*. No public import path moved and the board is not
exported, like `HandoffClaim` beside it.
**"The same record threaded through that function" was half the fix**, and a real sidecar is what
said so. The reachable misconfiguration is a tier named in `CORTEX_SWAP_EVICT_MODELS` that the
daemon has no artifact for, and such a tier is not in its roster at all: it answers 404 to the
**status** of the clearing loop, several calls before the `start` this entry named. Witnessed
live on 2026-08-09 against the real `model-host` image over real HTTP, which answered
`settled=False` with an empty record while `GET /models/cortex` on the same daemon read `ready`,
and answered `settled=True` with `missing=('subagent-gpu',)` once the clearing loop was
peer-tolerant too. The children were stub HTTP servers, no GGUF being mountable that session;
everything this touches is control plane.
**The detail line had to stop naming a cause.** `TIERS_MISSING_DETAIL` said a tier "did not come
back after a deep task", which is false on a brain that has never escalated, so it now reads
`the model host is not running {models}, so delegated work is running on the CPU`. The record
grew a second writer, so its sentence had to describe the state rather than one writer's story.
What it leaves is the deep tier's own clearing, the entry below.

## Trail

- 2026-08-09: Opened by the tier-outage close, which refuses that conflation everywhere else and
  left this one site alone.
- 2026-08-09: Landed hours later and ahead of its trigger, recorded at the
  [ADR-0030 boot-verdict addendum](../../adr/ADR-0030-brain-handoff.md). Its stated blocker was still
  exactly true, `residency.py` standing at 299 of 300, so the fix began with the split it named,
  taken by responsibility rather than by count as `ResidencyBoard`. One entry opened in its place,
  the deep tier's own clearing.
- 2026-08-09: What the entry's text could not know is which call a real deployment fails at, and a
  real sidecar over real HTTP said so: a tier named in `CORTEX_SWAP_EVICT_MODELS` with no artifact
  is not in the daemon's roster, so it answers 404 to the `status` the clearing loop asks first,
  several calls before the `start` the entry named, and the boot answered `settled=False` while the
  cortex read `ready` on that same daemon.
- 2026-08-09: The area header held its number at 7 and its set moved without it, so for a stretch
  that line named this closed entry and missed the deep tier's own clearing that had taken its
  place, the total staying right across both errors. That is the failure the index's third warning
  describes, and it was caught by re-reading the entries rather than the arithmetic.
