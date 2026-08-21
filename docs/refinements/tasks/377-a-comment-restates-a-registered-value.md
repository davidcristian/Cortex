# A compose comment restates a registered value and nothing holds it there

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-21 by the close of [R-333](333-compose-defaults-that-restate-a-declaration.md), the
survey that read every `${CORTEX_*:-default}` under `docker/`. The survey sorted the
**substitutions**. It did not sort the **comments** above them, and two of those quote a number the
survey then registered on the other side of the tree.

`docker/docker-compose.body.yml` explains why the brain's capture edge defaults to 2048 by saying
that `CORTEX_IMAGE_MAX_TOKENS=1024` on the model host "gives the encoder somewhere to put them".
`docker/docker-compose.gpu.yml` explains the token budget by saying it is the default "together
with `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` on the brain". Each file's prose states the other file's
value, and the pair is the argument for both numbers, so a retune of either leaves one comment
telling a reader a fact the tree stopped holding. Both values are registered: the capture edge
against `DEFAULT_CAPTURE_MAX_EDGE` and the token budget against `DEFAULT_IMAGE_MAX_TOKENS`. What is
unheld is the sentence, not the setting.

By the rule the survey settled this is a far side rather than history: the comments say what the
deployment does now, so a value moving makes each of them **wrong** rather than **past**. So the
gap is a registration and not a decision, which is why this is filed narrow.

**What makes it more than a missing row.** A mention today is matched inside a file the scan
already reads for its substitution, and a comment quotes the value in a shape the substitution
never takes: `CORTEX_IMAGE_MAX_TOKENS=1024` is the variable and its value joined by an equals sign,
which is neither the `${VAR:-1024}` form the compose reader looks for nor a bare literal on a line
of its own. So the work is to decide what a mention in prose looks like to `scripts/values.py` and
whether a comment is a distinct spelling or just another place a whole value may appear. That is
the same question a runbook sentence already answered once, which is why the answer is likely to
be a mention rather than a form: what changes here is only that the file it lives in is one the
compose reader also opens for a different purpose.

Deliberately not fixed by deleting the cross reference. The two numbers only make sense together,
which is the measured pairing the vision runbook records, and a comment that stopped naming its
partner would be cheaper to hold and worth less to read.

## Trail

- 2026-08-21: opened by the close of
  [R-333](333-compose-defaults-that-restate-a-declaration.md), which registered both numbers and
  left the two comments that argue for them naming each other unheld.
