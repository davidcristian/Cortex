# The accepted residual risk the redaction cannot catch

**Status:** declined 2026-07-19
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Strict redaction removes a URL the model reproduces. It cannot catch one the model retypes with a
space, defangs, or describes in words. The opaque bit closes the transcription path, not the
paraphrase path, and no output filter closes the paraphrase path.

Declined because it names no work: it is an accepted limitation with no fix on offer, and it is
kept here as the record of what was accepted and why. It reopens only if someone proposes a
mechanism that closes the paraphrase path, which would be a different kind of defence than an
output filter. ADR-0029's Deferred paragraph lists it beside the rest.

## History

- 2026-07-19: A bookkeeping pass found this entry missing from the area's open items with nothing
  saying why, and stated the exclusion here: it is excluded because it names no work, and an
  accepted limitation with no fix on offer would otherwise sit forever in a backlog that must be
  empty before the README ships.
- 2026-08-16: Narrowed, not reopened. The "retypes with a space" case was measured and closed for
  an anchored URL by the split host (ADR-0058 decision 8), so a reply writing `hxxp://evil dot com`
  is now redacted. The entry stands for the paraphrase path it is really about, a URL described in
  words with no scheme in front of it.
