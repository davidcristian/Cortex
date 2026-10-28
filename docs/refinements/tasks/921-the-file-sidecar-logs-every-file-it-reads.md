# The file sidecar logs every file it reads

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-28

On 2026-10-28, on the `cortexn9` stack, a turn read a `deploy.env` holding a database password, a
`STRIPE_SECRET_KEY` and an `SMTP_PASSWORD` through `read_text_file`. The brain logged none of the
values, and the reply named none. The filesystem sidecar logged all of them: `supergateway` runs at
its default `--logLevel info`, which writes every message between the brain and the server to
stdout, so `docker logs` of the sidecar holds a `[supergateway] Child → StreamableHttp:` line with
the whole file. Every file the cortex reads ends up in a container log that the brain's redaction
never sees.

`supergateway@4.1.0` offers `debug`, `info` and `none`. At `info` it writes the messages with
`console.log` (stdout) and its errors (`Child exited`, `Child stderr`, failed sends) with
`console.error` (stderr). The compose file's comment says "every call it makes is logged", and the
runbook tells an operator to watch for the `Listening on port` line, which is also on stdout.

Reproduction: section "A key file read through the file tools" of
[overlay-privacy-flows.md](../../readings/overlay-privacy-flows.md).

## What to do

1. Drop the message lines and keep the errors: either `--logLevel none` with a startup check that
   does not read the log, or stdout sent to `/dev/null` in the sidecar's command so stderr stays.
   Update the compose comment and the runbook's `Listening` step to match.
2. Repeat the reproduction and count the secret in the sidecar's log (pass: 0 lines), then stop the
   server child and check the error line still reaches `docker logs`.

## History

- 2026-10-28: filed from the privacy flows on the `cortexn9` stack.
