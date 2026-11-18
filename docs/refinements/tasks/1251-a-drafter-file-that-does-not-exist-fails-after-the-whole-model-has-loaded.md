# A drafter file that does not exist fails after the whole model has loaded

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-18

`ModelHostConfig` (`brain/packages/model_manager/src/cortex_model_manager/config.py`) turns
`CORTEX_MODEL_FILE_CORTEX_DRAFT`, `CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT` and
`CORTEX_MODEL_FILE_BRAIN_DRAFT` into a `--model-draft` path and does not check that the file is
there. The engine loads the tier's whole model first, then fails on the drafter and exits with
code 1. For the cortex and each GPU subagent server the daemon's restart budget starts it again, so
the tier loads its whole file once per attempt and never serves.

The daemon's own lines do not name the cause: `GET /models/cortex` reads `loading`, then
`failed` with `the process exited with code 1`, then `loading` again, and the log has
`a model process exited without being asked to; starting it again`. Only the engine's lines
name the file: `failed to load draft model, '/models/nowhere/none.gguf'`.

The other settings of 2026-11-18 fail at once or start in the documented shape. A server count
of 0, a draft length of 0, an empty count and a cache type other than `f16` or `q8_0` are each
refused when the settings are read, with the variable named. An empty drafter setting starts the
tier with no drafter flags. A server count of 3 adds `subagent-gpu-3` on the next port. Two slots
on a file `drafters.py` does not list start without the named drafter and
`ModelHostConfig.undrafted` names it for the warning.

## Reproduction

Drawn on 2026-11-18: the model host alone with
`CORTEX_MODEL_FILE_CORTEX_DRAFT=nowhere/none.gguf`. Log:
`~/.cache/cortex-run/2026-11-18/slot8/logs/stepe.txt`. The settings cases above were read in one
process from `ModelHostConfig` with each variable set in turn.

## What would close it

Check each named file under `models_root` when the settings are read, the tier's model file and
its projector as well as its drafter, and refuse the settings with the variable and the path
named. The models mount is in the container when the daemon starts, so the check needs no new
port. A drafter that is the tier's own model file needs no second check.

## History

- 2026-11-18: filed by the audit of the tier drafter settings.
