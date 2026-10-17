# A sidecar names a malformed setting by its field

**Status:** done 2026-10-17
**Area:** brain
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

The brain reads its settings through `read_settings` (`cortex_orchestrator/settings_read.py`), so a
malformed value ends it with one `setting refused` line naming the variable and never the value.
The model host and the email sidecar still construct their settings directly:
`ModelHostConfig()` in `cortex_model_manager/server.py` `main`, and `EmailConfig()` and
`SmtpConfig()` in `cortex_email/server.py` `main`. A malformed `CORTEX_MODELHOST_*` or
`CORTEX_EMAIL_*` value still ends that container with a traceback naming the field, and a
validator's `ValueError` text there includes the input.

## What to do

1. Move the reader to a package both sidecars may import. `cortex_core` has no pydantic
   dependency today, so this is either a new dependency there or a small shared package.
2. Read each sidecar's classes through it, and log the refusal as one line with exit 1. The model
   host reads `ModelHostConfig` before `configure_logging`, so its refusal needs the default
   rendering.
3. Test each class with a malformed value, asserting the variable named and the value absent.

## History

- 2026-10-16: filed by the brain's settings reader, which covered the brain's classes only.
- 2026-10-17: done. The premise held and was worse than written: with send enabled, a password
  and no user, `SmtpConfig()` printed the password in the traceback's input dict. The reader moved
  to a new package, `cortex_settings`, rather than `cortex_core`, which imports only the standard
  library, so the email sidecar imports the reader without the core. Both sidecars read every class
  through it and exit 1 with one `setting refused` line: the model host's in `plain` at INFO, the
  email sidecar's through the standard library's last-resort handler with the reason inside the
  message. No other Python sidecar exists: the file sidecar is the Node filesystem server and the
  embedder is `llama-server`. An unknown log rendering is refused the same way, by a check on the
  field that reads the core's one list of renderings. The model host's log level is still checked
  outside the reader, filed as [R-892](892-the-model-host-log-level-is-checked-outside-the-settings-reader.md),
  and the reader's mask garbles a reason whose own words contain the value, filed as
  [R-893](893-a-masked-value-inside-a-reasons-own-words-garbles-them.md).
