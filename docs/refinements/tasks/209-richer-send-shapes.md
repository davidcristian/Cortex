# Richer send shapes

**Status:** done 2026-07-13
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

cc, bcc and HTML, recorded at [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md) decision 9.
`EmailSender.send` takes a frozen `EmailDraft` value (to, subject, body, plus optional cc, bcc and
html), so the addition goes on a value object rather than a wider signature. cc and bcc get the
recipient's CR/LF header-injection refusal, a bcc is stripped from the transmitted message by the
stdlib's `send_message`, and html composes a `multipart/alternative`. It is entirely inside the
sidecar behind the unchanged brain-side confirmation, and the live round-trip now exercises cc and
html.

## History

- 2026-07-13: Closed with the richer draft value.
