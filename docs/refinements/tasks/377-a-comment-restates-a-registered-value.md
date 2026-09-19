# A compose comment restates a registered value and nothing checks it

**Status:** done 2026-08-22
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

The survey that read every `${CORTEX_*:-default}` under `docker/` sorted the substitutions. It did
not read the comments above them, and two of those quote a number the survey then registered on the
other side of the tree.

`docker/docker-compose.body.yml` explains why the brain's capture edge defaults to 2048 by saying
that `CORTEX_IMAGE_MAX_TOKENS=1024` on the model host gives the encoder somewhere to put them.
`docker/docker-compose.gpu.yml` explains the token budget by saying it is the default together with
`CORTEX_BODY_CAPTURE_MAX_EDGE=2048` on the brain. Each file's prose states the other file's value,
and the pair is the argument for both numbers, so a retune of either leaves one comment telling a
reader a fact the tree stopped holding. Both values are registered, the capture edge against
`DEFAULT_CAPTURE_MAX_EDGE` and the token budget against `DEFAULT_IMAGE_MAX_TOKENS`. What is
unchecked is the sentence.

By the rule the survey settled this counts, since the comments say what the deployment does now, so
a value moving makes each of them wrong rather than historical.

What makes it more than a missing row is that a comment quotes the value in a form the substitution
never takes: `CORTEX_IMAGE_MAX_TOKENS=1024` is the variable and its value joined by an equals sign,
which is neither the `${VAR:-1024}` form the compose reader looks for nor a bare literal on a line
of its own. So the work is to decide what a mention in prose looks like to `scripts/values.py`.

Deliberately not fixed by deleting the cross reference. The two numbers only make sense together,
which is the measured pairing the vision runbook records.

## History

- 2026-08-21: Opened by the close of
  [R-333](333-compose-defaults-that-restate-a-declaration.md), which registered both numbers and
  left the two comments that argue for them naming each other unchecked.
- 2026-08-22: Done, and this entry's reading was right: a comment is neither a new value form nor a
  second written form, only another place a whole value appears. A mention was never syntax, being
  a template rendered and required to appear as a token of its own, so the runbook sentence that
  answered this once, `CORTEX_BODY_CAPTURE_MAX_EDGE={value}`, is the same shape a compose comment
  writes, and `scripts/values.py` needed nothing at all. The only new thing is the file, and the
  scan never asks what else a file is for, so the body override has a substitution of one value and
  a mention of another with nothing to reconcile. Both quotes were confirmed word for word and both
  numbers were already registered, so the work was two rows and their reasons. Answered together
  with [R-354](354-two-declared-defaults-the-reducer-refuses.md), which is where the reducer's half
  went; testing this half's reading against that one is what kept a comment from being given a
  value form it does not need. Two planted differences, one per row, each exiting 1 and restored
  byte for byte, inside the sixteen the boolean form was recorded with. One narrower task opens for
  the same pairing where it is argued rather than shipped,
  [R-382](382-the-paired-numbers-quoted-in-prose.md).
