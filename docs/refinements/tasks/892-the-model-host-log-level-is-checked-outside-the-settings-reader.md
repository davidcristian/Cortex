# The model host's log level is checked outside the settings reader

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-10-17

`ModelHostConfig.log_level` is a plain `str`, so `read_settings` accepts any value. `main` in
`cortex_model_manager/server.py` then passes it upper-cased to `configure_logging` and as given to
`uvicorn.run`. An unknown name such as `CORTEX_MODELHOST_LOG_LEVEL=loud` ends the model host with a
traceback ending `ValueError: Unknown level: 'LOUD'` instead of one `setting refused` line naming
the variable. A name the standard library knows but uvicorn does not, such as `INFO` in capitals,
passes `configure_logging`, logs `model host configured`, and then fails inside `uvicorn.run`,
because uvicorn's `LOG_LEVELS` keys are lowercase.

## What to do

1. Check the field while the settings are read, against `uvicorn.config.LOG_LEVELS` so the list
   has one source, the way the rendering is checked by `known_log_format`.
2. Test `main` with an unknown name and with `INFO`, asserting one `plain` line naming the variable
   and exit 1.

## History

- 2026-10-17: filed by the close of
  [R-890](890-a-sidecar-names-a-malformed-setting-by-its-field.md). Run from the working tree with
  `CORTEX_MODELHOST_LOG_LEVEL=loud`, `python -m cortex_model_manager` exits 1 with a traceback.
