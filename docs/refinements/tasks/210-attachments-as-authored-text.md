# Attachments as authored text

**Status:** landed 2026-07-15
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Attachments are recorded at the [ADR-0022 attachments
addendum](../../adr/ADR-0022-email-write-confirmer.md), as authored text. This entry framed the open
question as a bytes-transport choice (a base64 blob versus a filesystem path, the latter needing a
mount *and* a file-read capability on a sidecar that deliberately has neither). Both candidates turn
out to be disqualified by something cheaper to check than their cost: this ADR's own
**`arguments_json` is the executed contract** rule. A path puts a *name* on the confirmation card
and reads the bytes after the click, from a filesystem that can change in between; base64 puts bytes
on the card that no human can read. So an attachment is `EmailAttachment(filename, content,
subtype="plain")` on the draft, composed as one `text/*` part each: the maintype is not a parameter
(as `From` is not), which makes the capability one sentence, namely the assistant attaches what it
**wrote**. Transport-free (tool arguments already arrive as JSON over MCP), so no new capability, no
proto/port/gate/taint change, and a draft without attachments is byte-for-byte the previous message.
Refused rather than truncated past five bounds in `SmtpSender._compose` (filename non-empty,
CR/LF-free, ≤ 128 chars; subtype a MIME token; ≤ 8 attachments; ≤ 32768 characters of content in
total), each mutation-proven. Two costs the entry did not predict, both small: ruff's `max-args = 6`
fires on the **advertised tool signature**, where the ceiling's own rationale (bundle
*collaborators*) does not apply, so it takes an inline `noqa` with that reason rather than folding
user-visible draft fields into an object the model would have to learn; and driving the card in a
browser found two pre-existing gaps an attachment is the first value to reach, namely
`.confirm-draft` having no height bound (the first argument *meant* to be long pushed Approve and
Deny out of view; now `max-height: 42vh` and scrolls) and non-string values being rendered with
`JSON.stringify` (so a file's newlines reached the user as `\n` escapes; now a generic
`formatDraftValue`, which handles JSON shapes and nothing about `send_email`). Remaining behind the
same seam: **bytes the assistant did not author** (a real file), which needs the capability grant
*plus* a way for the card to bind approval to a payload the user cannot read (a digest and size
shown, the sidecar re-reading at send and refusing on mismatch); and **per-field schema
descriptions** inside the nested object. Verified over a real sidecar rather than assumed: pydantic
lifts the `EmailAttachment` **docstring** into the `$defs` entry's `description`, so the model is
already told what an attachment is and is not; only per-field prose would need
`Field(description=...)`, and that would put pydantic in the pure values module to say what the type
names already say.
**Real-file attachments (bytes the assistant did not author) declined 2026-07-16 ([ADR-0022
real-file addendum](../../adr/ADR-0022-email-write-confirmer.md)).** The capability stays ungranted:
the email sidecar keeps no filesystem access and `send_email` keeps attaching only authored text.
Read against the code first. Send exists and attaches text the model wrote
(`EmailAttachment.content` is a `str` composed as a `text/<subtype>` part in `cortex_email/smtp.py`,
the tool docstring telling the model "a file on disk cannot be attached"); the `mcp-email` service
declares no `volumes:` in `docker/docker-compose.email.yml`, so "a real file" means granting the one
outbound sidecar the new power to read local disk. That fuses read-local with write-remote in the
process whose job is to leave the machine, the exfil-via-`send_email` surface the tainted block
(`cortex_core/dispatch.py`) exists to deny. The deeper finding is that the taint boundary already
closes the *useful* path: reading a file's bytes into the turn taints it (`ToolResult` defaults
`UNTRUSTED`, `TaintLedger.mark` flips the turn, a gated call on a tainted turn is `DENIED_MSG` with
the confirmer unconsulted), so a real-file attachment is only useful if the bytes reach the sidecar
without entering the model's context, which is exactly the arbitrary-file exfiltration channel. A
digest-bound card binds approval to the *bytes* (catching a swap between click and send) but never
to the file *choice*, and the choice is what an injection controls, the same "the card makes the
user the target" failure that declined confirm-with-provenance the same day. The safe design, if a
consumer ever needs it, is recorded at the ADR addendum: a narrowly-scoped source (an allowlisted
outbox mount or an opaque handle, never an arbitrary path), the file choice gated by taint so
injected content cannot pick it, and the digest-bound card on top, which is a slice and the right
shape only when something needs it. Moves to the index's dead-until-a-consumer list.
**Per-field schema descriptions landed 2026-08-11 ([ADR-0022 per-field
addendum](../../adr/ADR-0022-email-write-confirmer.md)).** The entry's verification was read against
the generated schema again before anything was written, as this backlog's own header demands, and it
held exactly as far as it went: the `$defs` entry does carry the docstring, and the three fields
under it carried `title` and `type` and nothing else, so a model was told there is a string called
`content` and left to guess what belongs in it. What the entry got wrong is the half-sentence at its
end, "to say what the type names already say", and the guesses it dismissed are not type-shaped.
**`content` is the one that costs most, because getting it wrong still succeeds:** `filename` beside
`content` reads like a name beside a location, and `{"filename": "notes.md", "content":
"/home/user/notes.md"}` composes, sends and arrives, the recipient receiving a file whose entire
text is a path, refused by nothing, because a path is a valid string. `subtype` reads as a field for
the whole MIME type, `text/markdown`, which is precisely what `_SUBTYPE_TOKEN` refuses, the solidus
being banned so `text/` stays a prefix the caller cannot escape. `filename` carries a 128-character
ceiling nobody would assume from `str`. And the array carried no description at all, though its two
bounds (`MAX_ATTACHMENTS`, and `MAX_ATTACHMENT_CHARS` summed over content) belong to neither the
object nor any one field, so they ride `attachments` itself through the tool signature, the
`capture_screen` target precedent. Each refusal lands in the sidecar, which is **after** the gate
and after the user approved the card, so a wrong guess costs a send the user consented to and did
not get, rather than a cheap retry. The entry's other objection, pydantic in the pure values module,
was answered by its own finding: the module has been a prompt surface since attachments landed, the
docstring being lifted from it, so the choice was between complete model-facing prose and half of
it, and the alternative of a schema-facing mirror in `server.py` would spell the tool contract twice
to keep one import out of one file. The three bounds moved to `values.py` with it, so the number a
model is told and the number `SmtpSender` enforces are one value read twice. Five mutations
measured, and the sixth is the finding: the subtype check first matched the bare `text/`, which the
description holds twice, in the instruction and in the counter-example warning against
`text/markdown`, so deleting the instruction left it green; it matches the locating phrase now. What
the entry claimed and this pass did **not** measure is the rate, whether a model composes a correct
call more often with the descriptions than without; that stays an argument resting on the four
guesses being real.

## Trail

- 2026-07-15: extracted from the ROADMAP's deferred-refinements section with the entry kept
  verbatim, and landed the same day as authored text, leaving two sub-items behind the same seam.
- 2026-07-16: the real-file sub-item (bytes the assistant did not author) closed as declined and
  the area count went from 5 to 4, the capability kept ungranted because send attaches only
  authored text, the `mcp-email` sidecar has no `volumes:` to read from, and granting the one
  outbound sidecar file-read would fuse read-local with write-remote on the exfil path. It moved
  to the index's dead-until-a-consumer list, where the safe design (a scoped source, the file
  choice gated by taint, the digest-bound card on top) is recorded for the consumer that reopens
  it.
- 2026-08-11: the per-field schema descriptions sub-item closed, the smallest thing this backlog
  held and one whose entry had never been read against the code, the reading being what made it
  work rather than decoration. The area count held at 4, one out and one in, the same sweep having
  found the read half's `query` unstated as a dialect and left it deferred for want of a live pass.
