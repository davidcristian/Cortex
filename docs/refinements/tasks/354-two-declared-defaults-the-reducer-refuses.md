# Two kinds of declared default the constant scan cannot compare

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-21 by the close of [R-333](333-compose-defaults-that-restate-a-declaration.md), the
survey that read every `${CORTEX_*:-default}` under `docker/`. Five of the fifty six are couplings
by every test the survey applied and are untied for one reason only: `scripts/values.py` will not
reduce the value.

**The booleans.** `CORTEX_EMAIL_IMAP_TLS_INSECURE`, `CORTEX_EMAIL_SMTP_TLS_INSECURE` and
`CORTEX_EMAIL_SEND_ENABLED` each default to `false` in `docker/docker-compose.email.yml`, and each
restates a field in `brain/packages/email/src/cortex_email/config.py` that declares `False`. Two of
the three are TLS escape hatches and the third is the send switch, so this is the set where a
default flipping to the unsafe answer in one place and not the other is worth catching. The reducer
reads strings, integers, decimals and one-line frozensets, and a bare `False` is none of them.
The casings differ too, so a boolean form would need a spelling the way docker's size suffix did:
Python writes `False` and YAML writes `false`, and neither can render the other's text.

**The signed integers.** `CORTEX_REASONING_BUDGET` and `CORTEX_REASONING_BUDGET_BRAIN` both default
to `-1` in `docker/docker-compose.gpu.yml`, and both restate `_UNRESTRICTED_REASONING` in
`brain/packages/model_manager/src/cortex_model_manager/config.py`. The scan would find that
declaration; `values.parse_value` refuses it, a leading sign being refused with everything else the
reducer will not guess at. The refusal was deliberate when the decimal form landed, on the ground
that no coupling then spelled one. Two do now.

**What would close it.** Either form is a value form plus its rule, the shape the decimal and the
frozenset already have: what reduces, what it renders as, and what an ordering may do with it. A
boolean has no ordering and needs a spelling; a signed integer has an ordering and needs none. Both
want the same proof the forms before them got, a planted drift per registered entry. The private
name is a second question worth a sentence: `_UNRESTRICTED_REASONING` is module private, and a
registry entry naming it would reach past that underscore, so either the constant loses it or the
registry states that a gate reads what a module hides.

## Trail

- 2026-08-21: opened by the close of
  [R-333](333-compose-defaults-that-restate-a-declaration.md), which sorted every compose default
  and found these five to be couplings the mechanism refuses rather than couplings nobody wanted.
