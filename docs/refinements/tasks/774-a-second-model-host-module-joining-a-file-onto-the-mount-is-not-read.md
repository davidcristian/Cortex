# A second model host module joining a file onto the mount is not read

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Trigger:** a module under `brain/packages/*/src` other than the model host's `config.py` reads
`models_root` or builds a path under the models mount. Countable with
`grep -rn models_root brain/packages/*/src`, which today finds `config.py` alone; a search for
`/models` also finds the control API's routes `/models/{model}` in `api.py` and `adapter.py`, which
are URLs and not the mount
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)
**Verified:** 2026-10-02

`artifactnames.tiered` reads one module, the model host's `config.py`, and in it the fields
`ModelHostConfig` hands to its resolver `_path`. A second module joining a file onto the mount,
such as `f"{config.models_root}/{config.some_file}"` in `server.py`, names an artifact this reader
never sees, so a variable outside the `CORTEX_MODEL_FILE_` family there is reported by nothing.

The fix is not a wider walk alone. A read of the mount outside the class that only reports it, on
`GET /health` or in a startup check, is allowed on purpose
([R-521](521-a-settings-method-reading-the-mount-for-anything-but-a-path-is-refused.md)), and the
shape of an expression does not tell a report from a join: an alias or a returned root passes any
rule that looks for a join. A fix that holds: walk every module of the model host's package, refuse
any read of `models_root` outside `_path`, and list each reporting read by module and function in
the scan with its reason, the way `settingscheck.EXEMPT` lists its omissions, so each one is a
reviewed diff.

## History

- 2026-10-02: opened because [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md) listed this
  case as recorded in the backlog when no task file named it. Found while declining
  [R-521](521-a-settings-method-reading-the-mount-for-anything-but-a-path-is-refused.md).
