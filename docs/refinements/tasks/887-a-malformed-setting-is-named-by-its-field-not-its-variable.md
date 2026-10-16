# A malformed setting is named by its field, not its variable

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-10-16

A brain started with a malformed setting exits within 2 s, which is correct, but with a Python
traceback of about 48 lines whose last line names the settings class's field. For
`CORTEX_TOOLS_GATED='[read_text_file'` it ends `SettingsError: error parsing value for field
"confirm_names" from source "EnvSettingsSource"`, and `confirm_names` appears in no compose file,
runbook or variable name. `CORTEX_SCHEDULE_TZ=Mars/Olympus` and `CORTEX_SEAM_PORT=23o51` end in a
`ValidationError` naming `ScheduleConfig` `tz` and `RpcServerConfig` `port`, which a reader maps
back to the variable only by knowing each class's prefix. A malformed `CORTEX_REDIS_URL` ended in
`ValueError: Port could not be cast to integer value`, naming nothing.

## Reproduction

`docker compose run --rm --no-deps -T -e 'CORTEX_TOOLS_GATED=[read_text_file' brain` on any stack
([startup readings](../../readings/startup-order-and-settings.md)).

## What to do

1. Read every settings class in one function the composition root calls first, and turn a
   `SettingsError` or `ValidationError` into one typed error whose text names the environment
   variable (prefix plus field, or the field's alias) and the reason, never the value.
2. Route it through the guard [R-664](664-a-startup-traceback-reaches-stderr-with-no-formatter.md)
   describes, so the container's last line is that one rendered line and the exit is non-zero.
3. Test each class with a malformed value, asserting the variable name in the text and the value
   absent from it.

## History

- 2026-10-16: filed by the startup flows' malformed settings.
