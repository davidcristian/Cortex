# Richer send shapes

**Status:** landed 2026-07-13
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

cc/bcc/HTML are recorded at the [ADR-0022 richer-send-shapes
addendum](../../adr/ADR-0022-email-write-confirmer.md). The `EmailSender.send` contract took a
frozen `EmailDraft` value (to/subject/body + optional cc/bcc/html), so the addition rides a
value object, not a wider signature; cc/bcc get the recipient's CR/LF header-injection refusal,
a bcc is stripped from the transmitted message by `send_message` (stdlib), and html composes a
`multipart/alternative`. Entirely inside the sidecar behind the unchanged brain-side gate
(still `send_email` in `CORTEX_TOOLS_GATED`, confirm card unchanged); CI-gated at 100% and the
live round-trip now exercises cc + html.
