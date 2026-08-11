# The accepted residual the guardrail cannot catch

**Status:** declined 2026-07-19
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Strict redaction removes a URL the model
reproduces. It cannot catch one the model **retypes with a space**, defangs, or describes in
words. The opaque bit closes the transcription path, not the paraphrase path, and no output
filter can close the latter.
**Excluded from this area's open count on purpose, stated 2026-07-19.** ADR-0029's own Deferred
paragraph lists it beside the rest, and it was missing from the Open items line above without
anything saying why, which is the silent kind of omission this file exists to catch. It is
excluded because it names no work: an accepted limitation with no fix on offer (no output filter
closes a paraphrase) would sit in a backlog that must be empty before the README ships and never
leave it. It stays here as the record of what was accepted and on what reasoning, which is the
role a declined entry plays, and it reopens only if someone proposes a mechanism that closes the
paraphrase path, which would be a different kind of defence than an output filter.

## Trail

- 2026-07-19: a bookkeeping pass found this entry missing from the area's Open items line with
  nothing saying why, which is the silent kind of omission this file exists to catch, and stated the
  exclusion on the bullet itself. ADR-0029's own Deferred paragraph lists it beside the rest. It is
  excluded from the area's open count because it names no work, an accepted limitation with no fix
  on offer would otherwise sit forever in a backlog that must be empty before the README ships, and
  it reopens only if someone proposes a mechanism that closes the paraphrase path.
