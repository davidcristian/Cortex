# The constant scan cannot tie a decimal

**Status:** landed 2026-08-19
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

`scripts/values.py` reduces a declaration's right-hand side to something two languages can be
compared on, and it accepts exactly three forms: a product of integer literals, a plain
double-quoted string, and a one-line `frozenset` of those strings. A decimal literal is refused
with everything else it will not guess at, which is the right default for a reducer (one that
guesses is a gate that agrees with itself) but leaves a whole class of value untiable.

The class is not hypothetical. Both deadlines on the `BodyService` seam are decimals:
`DEFAULT_CAPTURE_TIMEOUT_S` (10.0) and `DEFAULT_CALL_TIMEOUT_S` (5.0) are declared in
`brain/packages/body_client/src/cortex_body_client/gateway.py` and spelled again as shell
substitution defaults in `docker/docker-compose.body.yml`
(`${CORTEX_BODY_CAPTURE_TIMEOUT_S:-10.0}`, `${CORTEX_BODY_CALL_TIMEOUT_S:-5.0}`). Retuning either
in the brain leaves every composed deployment running the old number with nothing saying so,
which is precisely the failure the salience limit's entry in `scripts/couplings.py` exists to
catch, and it cannot be registered the same way today. `docs/runbooks/vision.md` spells both a
third time.

The work is a reducer arm plus its rendering, and the second half is where the care goes: a
reading has to compare `5.0` to `5.0` without deciding that `5` and `5.0` are the same site (they
are the same number and different text, and a `Mention` needs the text to find its needle). The
honest shape is probably to reduce a decimal to its literal digits rather than to a float, so
comparison stays textual and no site can drift into a spelling the rendered needle would miss.
Whichever way it goes, prove it fails before trusting it: change one side of a registered decimal
pair and watch the scan redden.

## Trail

- 2026-08-18: Opened by the close of [R-264](264-uniform-per-call-deadline.md), which added the
  second decimal to this seam and found the scan could not hold either of them.
- 2026-08-19: Landed as a fourth value form in `scripts/values.py`. A decimal reduces to
  `Digits`, a one-field named tuple holding the characters it is written with, so the comparison
  stays textual and `5` never passes for `5.0`; its own type rather than a `str`, so it cannot tie
  to a string literal spelling the same characters. Digits, one point, digits, with `_` grouping
  either run; a leading or trailing point, a sign, an exponent and a Rust type suffix are refused.
  An ordering still compares integers and now says so, a decimal under one being a fault rather
  than a guess. Both deadlines are registered, each with one site and four mentions (the compose
  default, [vision.md](../../runbooks/vision.md), [body-volume.md](../../runbooks/body-volume.md)
  and [brain-body-client.md](../../modules/brain-body-client.md)); the origin ADR is deliberately
  not among them, a decision record having to go on saying what was decided after the number
  moves. Proved able to fail four times on the real tree: the site retuned to `5.5`, the same site
  retyped as `5`, the compose default alone at `12.0`, and the runbook cell alone at `30.0`, each
  exiting 1, where the reducer at the previous commit raised on `10.0` and the entries could not
  be written at all. The close cost a file, `scripts/couplings.py` splitting on the seam its own
  first sentence named: the entries moved to `scripts/seamcouplings.py` and the vocabulary stayed
  behind. What it leaves open is narrower and filed as
  [R-314](314-decimal-form-refusals.md); [R-306](306-subagent-memory-budget-spelled-twice.md)
  loses half of what blocked it. Written up in the ADR's 2026-08-19 addendum.
