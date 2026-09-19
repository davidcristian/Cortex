# A model host refusal claims to be the only record of itself

**Status:** done 2026-08-21
**Area:** inference-model-manager
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`_refused` in `brain/packages/model_manager/src/cortex_model_manager/api.py` has the level that
used to be on a second line, and its docstring argued for that level with a claim about reach: a
swap's eviction meets the 503 through the brain's own port, the brain turns it into a note without
logging its text, "so this line is the only record of it anywhere".

The level is right and the claim is wider than the tree supports. It holds for the swap in
eviction. It does not hold for the swap back: `restore_standing` in
`brain/packages/core/src/cortex_core/residency_moves.py` logs both of its failures with
`_logger.exception`, so the traceback reaches the brain's own log, and the `ModelHostError` in it
was built in `brain/packages/model_manager/src/cortex_model_manager/adapter.py` out of the status
code and the first 200 characters of the daemon's response body.

Nothing behaves wrongly. What is wrong is a docstring that will be read as a survey when somebody
next asks whether a line can be dropped or made quieter. The fix is to narrow the sentence to the
path it is true of and say that the restore path does pass the text on in a traceback.

## History

- 2026-08-20: Opened by a review of the change that removed the second, louder line at the raise,
  which found the surviving docstring's uniqueness claim true of the eviction and false of the
  restore.
- 2026-08-21: Fixed as ADR-0053 decision 5, wider than the entry asked for. The claim was checked
  first and held exactly. What the entry named two paths, the close traced as seven callers of the
  per-model routes, of which six log the daemon's sentence themselves (the unrostered preflight,
  the swap back, the peer restart, the peer review pass, the regain pass and boot recovery) and one
  keeps nothing (the swap in, whose conductor replies with a fixed note without reading the error).
  The docstring, `docs/modules/brain-model-manager.md` and
  [ADR-0051](../../adr/ADR-0051-log-line-rendering.md) all say that now; the level rule is
  unchanged and rests on what a 5xx means. The one caller that keeps nothing keeps nothing
  brain-side at all, filed as [R-350](350-a-failed-swap-in-says-nothing-brain-side.md).
