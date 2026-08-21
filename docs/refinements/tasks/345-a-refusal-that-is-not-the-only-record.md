# A model host refusal claims to be the only record of itself

**Status:** landed 2026-08-21
**Area:** inference-model-manager
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-20 by a review of the change that stopped the model host daemon logging a wedged
child's sentence twice. `_refused` in
`brain/packages/model_manager/src/cortex_model_manager/api.py` now carries the level that used to
ride the second line, and its docstring argues for that level with a claim about reach: a swap's
eviction meets the 503 through the brain's own port, the brain turns it into a note without logging
its text, "so this line is the only record of it anywhere".

The level is right and the argument is wider than the tree supports. It holds for the swap in
eviction. It does not hold for the swap back: `restore_standing` in
`brain/packages/core/src/cortex_core/residency_moves.py` logs both of its failures with
`_logger.exception`, so the traceback lands in the brain's own log, and the `ModelHostError` it
carries was built in `brain/packages/model_manager/src/cortex_model_manager/adapter.py` out of the
status code and the first 200 characters of the daemon's own response body. The daemon's sentence
therefore reaches the brain's log intact on that path, and the daemon's line is a second copy of it
rather than the only one.

**Why it matters at all.** Nothing behaves wrongly. What is wrong is a docstring that will be read
as a survey when somebody next asks whether a line can be dropped or quietened, which is exactly
the question the change it documents was answering. A claim of uniqueness that is true of one caller
and false of another is the kind that gets cited rather than re-derived.

**What would close it.** Narrow the sentence to the path it is true of, naming the eviction the
brain turns into a note, and say that the restore path does carry the text onward in a traceback, so
the reach of the two differs and the level still has to stand on its own. One paragraph, no code.

## Trail

- 2026-08-20: opened by a review of the change that removed the second, louder line at the raise,
  which found the surviving docstring's uniqueness claim true of the eviction and false of the
  restore.
- 2026-08-21: Landed as the ADR-0030 refusal-reach addendum, wider than the entry asked for. The
  entry's claim was re-derived first and held exactly: the docstring still said "the only record of
  it anywhere", `restore_standing` still logs both failures with `_logger.exception`, and the
  message in that traceback is still the one `HttpModelHost._request` builds out of the daemon's
  own response body. What the entry named two paths, the close traced as seven callers of the
  per-model routes, of which six log the daemon's sentence themselves (the unrostered preflight,
  the swap back, the peer restart, the peer sweep, the regain pass and boot recovery) and one keeps
  nothing (the swap in, whose conductor answers a fixed note without reading the error). The
  docstring, `docs/modules/brain-model-manager.md` and the ranked-recall record's raised-and-logged
  addendum all now say that; the level rule is unchanged and rests on what a 5xx means. The one
  caller that keeps nothing keeps nothing brain-side at all, filed as
  [R-350](350-a-failed-swap-in-says-nothing-brain-side.md).
