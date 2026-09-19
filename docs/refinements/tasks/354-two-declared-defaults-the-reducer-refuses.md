# Two kinds of declared default the constant scan cannot compare

**Status:** done 2026-08-22
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

The survey that read every `${CORTEX_*:-default}` under `docker/` found five of the fifty six to be
pairs by every test it applied, unregistered for one reason: `scripts/values.py` will not reduce
the value.

The booleans. `CORTEX_EMAIL_IMAP_TLS_INSECURE`, `CORTEX_EMAIL_SMTP_TLS_INSECURE` and
`CORTEX_EMAIL_SEND_ENABLED` each default to `false` in `docker/docker-compose.email.yml`, and each
restates a field in `brain/packages/email/src/cortex_email/config.py` that declares `False`. Two of
the three turn off TLS verification and the third is the send switch, so this is the set where a
default flipping to the unsafe answer in one place and not the other is worth catching. The reducer
reads strings, integers, decimals and one-line frozensets, and a bare `False` is none of them. The
casings differ too, so a boolean form needs a second written form the way docker's size suffix did:
Python writes `False` and YAML writes `false`.

The signed integers. `CORTEX_REASONING_BUDGET` and `CORTEX_REASONING_BUDGET_BRAIN` both default to
`-1` in `docker/docker-compose.gpu.yml`, and both restate `_UNRESTRICTED_REASONING` in
`brain/packages/model_manager/src/cortex_model_manager/config.py`. `values.parse_value` refuses a
leading sign, which was deliberate when the decimal form was added, on the ground that no pair then
used one. Two do now.

Either form is a value form plus its rule: what reduces, what it renders as, and what an ordering
may do with it. A boolean has no ordering and needs a second written form; a signed integer has an
ordering and needs none. The private name is a second question: `_UNRESTRICTED_REASONING` is module
private, and a registry entry naming it reaches past that underscore.

## History

- 2026-08-21: Opened by the close of
  [R-333](333-compose-defaults-that-restate-a-declaration.md), which sorted every compose default
  and found these five to be pairs the mechanism refuses rather than pairs nobody wanted.
- 2026-08-22: Fixed as both forms, answered together with
  [R-377](377-a-comment-restates-a-registered-value.md) so the reducer and the mention grammar came
  out as one design. A boolean reduces to `values.Truth`, the word it is written with, for the
  reason a decimal reduces to its digits and for one Python adds: `bool` is `int` here, so a bare
  `False` would match a declaration of zero and would sort under an ordering. A declaration may use
  Python's two words only, a second casing at a declaring site being two texts for one answer, and
  the far side that writes another is reached by the third form, `Spelling.LOWERED`. A signed
  integer is not a new form but a widening of the integer one: the sign is the expression's and
  never a factor's, a leading `+` stays refused, and the value has an ordering and needs no second
  form. This entry's account of the blocker was half of it: the three fields are indented, so the
  scan could not have read them whatever the reducer learned, and `tls_insecure` is declared in
  both settings classes. Two module constants were added, `DEFAULT_TLS_INSECURE` (one name for both
  switches, since one that ships open is not a safeguard) and `DEFAULT_SEND_ENABLED`. The private
  name keeps its underscore: a `Site` names what a file declares, not what a module exports, so the
  scan reads `_UNRESTRICTED_REASONING` as text and the rule is written on `Site` itself, the
  alternative being an API widened to suit its reader. One rule was corrected on the way: a second
  written form owes a faithful reading beside it only when it loses information, which a case fold
  does not, so `Spelling.lossy` is now the question `values.spelling_fault` turns on. Three
  entries, sixteen planted differences, all exiting 1 and all restored byte for byte; the registry
  gained a sixth part, `scripts/emailcouplings.py`, the first added as a subject rather than as a
  split, and `values.py` split at the cap into itself and `scripts/readings.py`. Recorded in
  ADR-0042. One narrower task opens from the other half of the pair,
  [R-382](382-the-paired-numbers-quoted-in-prose.md).
