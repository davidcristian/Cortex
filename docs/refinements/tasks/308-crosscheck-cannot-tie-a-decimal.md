# The constant scan cannot compare a decimal

**Status:** done 2026-08-19
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`scripts/values.py` reduces a declaration's right-hand side to a form two languages can be compared
on, and it accepted exactly three: a product of integer literals, a plain double-quoted string, and
a one-line `frozenset` of those strings. A decimal literal was refused along with everything else
the reducer will not guess at. Refusing is the right default, because a guessed reduction would
report two values as equal that were never compared, but it left a whole class of value
unregisterable.

Both deadlines on the `BodyService` boundary are decimals: `DEFAULT_CAPTURE_TIMEOUT_S` (10.0) and
`DEFAULT_CALL_TIMEOUT_S` (5.0) are declared in
`brain/packages/body_client/src/cortex_body_client/gateway.py` and written again as shell
substitution defaults in `docker/docker-compose.body.yml` (`${CORTEX_BODY_CAPTURE_TIMEOUT_S:-10.0}`
and `${CORTEX_BODY_CALL_TIMEOUT_S:-5.0}`). `docs/runbooks/vision.md` has both a third time. Retuning
either in the brain left every composed deployment on the old number with nothing reporting it.

The work is one more value form plus its rendering. The care goes into the second half: `5.0` must
compare against `5.0` without `5` and `5.0` being treated as the same text, since a `Mention` needs
the text to find it in a file. Reducing a decimal to its literal digits rather than to a float
keeps the comparison textual.

## History

- 2026-08-18: Opened by the close of [R-264](264-uniform-per-call-deadline.md), which added the
  second decimal to this boundary and found the scan could not check either of them.
- 2026-08-19: Fixed as a fourth value form in `scripts/values.py`. A decimal reduces to `Digits`, a
  one-field named tuple holding the characters it is written with, so the comparison stays textual
  and `5` never passes for `5.0`; it is its own type rather than a `str`, so it cannot match a
  string literal with the same characters. The form is digits, one point, digits, with `_` grouping
  allowed in either run; a leading or trailing point, a sign, an exponent and a Rust type suffix
  are refused. An ordering still compares integers and now says so, a decimal under one being an
  error rather than a guess. Both deadlines are registered, each with one declaration and four
  mentions (the compose default, [vision.md](../../runbooks/vision.md),
  [body-volume.md](../../runbooks/body-volume.md) and
  [brain-body-client.md](../../modules/brain-body-client.md)); the origin ADR is deliberately not
  among them, since a decision record has to go on saying what was decided after the number
  changes. Proved able to fail four times on the real tree: the declaration retuned to `5.5`, the
  same declaration retyped as `5`, the compose default alone at `12.0`, and the runbook cell alone
  at `30.0`, each exiting 1, where the previous reducer raised on `10.0` and the entries could not
  be written at all. The close cost a file: `scripts/couplings.py` passed the line cap, so the
  entries moved to `scripts/seamcouplings.py` and the shared vocabulary stayed behind. What it
  leaves open is filed as [R-314](314-decimal-form-refusals.md);
  [R-306](306-subagent-memory-budget-spelled-twice.md) loses half of what blocked it. Written up in
  ADR-0042.
