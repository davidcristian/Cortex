# A sidecar names a malformed setting by its field

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-10-16

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
