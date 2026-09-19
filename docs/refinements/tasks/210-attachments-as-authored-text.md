# Attachments as authored text

**Status:** done 2026-07-15
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Attachments shipped as authored text, recorded at
[ADR-0022](../../adr/ADR-0022-email-write-confirmer.md) decision 10. The entry framed the open
question as a bytes-transport choice, a base64 blob against a filesystem path, and both are
disqualified by this ADR's own rule that `arguments_json` is the executed contract. A path puts a
name on the confirmation card and reads the bytes after the click, from a filesystem that can change
in between; base64 puts bytes on the card that no human can read.

So an attachment is `EmailAttachment(filename, content, subtype="plain")` on the draft, composed as
one `text/*` part each. The maintype is not a parameter, which makes the capability one sentence: the
assistant attaches what it wrote. Nothing new is transported, since tool arguments already arrive as
JSON over MCP, so there is no new capability and no proto, port or taint change, and a draft without
attachments is byte for byte the previous message. Five bounds in `SmtpSender._compose` refuse rather
than truncate: filename non-empty, CR/LF-free and at most 128 characters; subtype a MIME token; at
most 8 attachments; at most 32768 characters of content in total.

Two costs the entry did not predict. Ruff's `max-args = 6` fires on the advertised tool signature,
where the limit's own rationale does not apply, so it takes an inline `noqa` with that reason rather
than folding user-visible draft fields into an object the model would have to learn. And driving the
card in a browser found two existing gaps an attachment is the first value to reach: `.confirm-draft`
had no height limit, so the first long argument pushed Approve and Deny out of view (now
`max-height: 42vh` with scrolling), and non-string values were rendered with `JSON.stringify`, so a
file's newlines reached the user as `\n` escapes (now a generic `formatDraftValue`).

Two sub-items followed.

**Real-file attachments were declined on 2026-07-16.** The `mcp-email` service declares no
`volumes:`, so "a real file" means granting the one outbound sidecar the power to read local disk.
That fuses read-local with write-remote in the process whose job is to leave the machine, which is
the exfiltration path the tainted refusal exists to deny. The taint boundary also already closes the
useful path: reading a file's bytes into the turn taints it, so a real-file attachment is only useful
if the bytes reach the sidecar without entering the model's context, which is exactly the
arbitrary-file exfiltration channel. A digest-bound card binds approval to the bytes but never to the
file choice, and the choice is what an injection controls. The safe design, if a consumer ever needs
it, is recorded in the same place: a narrowly scoped source (an allowlisted outbox mount or an opaque
handle, never an arbitrary path), the file choice refused on a tainted turn, and the digest-bound
card on top.

**Per-field schema descriptions shipped on 2026-08-11** (ADR-0022 decision 12). The `$defs` entry
does include the class docstring, as the entry said, but the three fields under it had `title` and
`type` and nothing else, so a model was told there is a string called `content` and left to guess
what belongs in it. The guesses are not type-shaped. `content` costs most, because getting it wrong
still succeeds: `{"filename": "notes.md", "content": "/home/user/notes.md"}` composes, sends and
arrives, the recipient receiving a file whose entire text is a path. `subtype` reads as a field for
the whole MIME type, `text/markdown`, which is precisely what `_SUBTYPE_TOKEN` refuses. `filename`
has a 128-character limit nobody would assume from `str`. And the array had no description at all,
though its two bounds belong to neither the object nor any one field, so they go on `attachments`
itself. Each refusal happens in the sidecar, after the user approved the card, so a wrong guess costs
a send the user consented to and did not get.

The objection about pydantic in the pure values module was answered by the entry's own finding: that
module has been a prompt surface since attachments shipped, the docstring being lifted from it. The
three bounds moved there too, so the number a model is told and the number `SmtpSender` enforces are
one value read twice. Five mutations were measured, and the sixth is the finding: the subtype check
first matched the bare `text/`, which the description contains twice, so deleting the instruction
left it green; it matches the locating phrase now. What was not measured is whether a model composes a
correct call more often with the descriptions than without.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section and closed the same day as
  authored text, leaving two sub-items behind.
- 2026-07-16: The real-file sub-item was declined, and the safe design recorded for the consumer that
  would reopen it.
- 2026-08-11: The per-field schema descriptions sub-item closed. It was the smallest thing this
  backlog held and one whose entry had never been read against the code, and the reading is what made
  it work. The same review found the read half's `query` unstated as a dialect and left it deferred
  for want of a live pass.
