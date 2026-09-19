# The substitution reader refuses a nesting compose expands

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Trigger:** a commit after 2026-08-30 renames a variable a compose file under `docker/` uses,
which is the change a two-variable fallback exists to cover. Checkable with
`git log -p -- 'docker/*.yml'`, reading for a variable name one commit removes while adding another;
the embedder's and the projector's model-file renames of 2026-08-30 are the only two so far, both
taken without a fallback
**Origin:** [ADR-0063](../../adr/ADR-0063-compose-checks.md)
**Verified:** 2026-09-19

`scripts/composedefaults.py` raises `SubstitutionReadError` on a nested expansion. Compose does
expand it: `${A:-${B:-x}}` resolves to `B`'s value and then to `x` on compose v2.39.1, measured
against the real binary. The refusal is kept with the true reason: the one rule reading a value
through this module, `defaultcheck.py`, compares a default as a value, and a nested default is a
second variable rather than a value, meaning one thing with nothing set and another once the
inner variable is set.

The refusal costs a form compose supports and this repo will want again. A two-variable fallback is
the one cheap way to rename an operator-facing compose variable without a deployment silently
falling back to a shipped default, which is the failure mode [AGENTS.md](../../../AGENTS.md) warns
about. Three options, cheapest first: read it and report the chain, so `defaultcheck.py` can compare
the literal tail; read it and report no value, returning the variable so its name is visible to
`artifactnames.py` and `subagentservers.py` while any rule asking for a value still raises; or keep
raising and record that as a decision. The readers of a variable's name and the readers of its value
are already different callers, so the middle option is a real choice.

## History

- 2026-08-30: opened by the close of
  [R-492](492-the-embedder-names-its-artifact-outside-the-family.md), which measured the docstring's
  claim false and declined the fallback anyway (a rejected alternative of
  [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)).
- 2026-09-09: claims checked again, and the correction had reached one of three places. The message
  the module raises still ended `which compose does not expand`, and so did the sentence in
  [repo-checks.md](../../modules/repo-checks.md); both are corrected here. The measurement was
  re-taken against the same binary: on Docker Compose v2.39.1, `docker compose config` over
  `OUT: "${A:-${B:-fallback}}"` prints `OUT: fallback` with neither set, `OUT: frominner` with `B`
  set, and `OUT: fromouter` with `A` set. The trigger has not fired: no compose file in `docker/`
  writes a nested substitution, over 76 variables read.
- 2026-09-14: still not fired. `composedefaults._braced` raises on a body containing a `{`, and the
  message now ends `whose default is itself a variable and so has no value for a rule over these
  spends to compare`. No compose file in `docker/` writes a nested substitution, over 78 variables
  read across the ten files.
- 2026-09-15: the reason the last reading recorded is itself false, and the measurement disproving
  it was one bullet above. It said a nested default has no value until a deployment supplies one,
  while the 2026-09-09 bullet records `${A:-${B:-fallback}}` printing `fallback` with nothing set.
  The measurement is re-taken and widened here on v2.39.1: `${A:-${B:-fallback}}`,
  `${A:-${B:-${C:-deep}}}`, `${A-${B-bare}}`, `${A:-${B}}` and `${A:+${B:-rep}}` print `fallback`,
  `deep`, `bare`, the empty string and the empty string with nothing set, and `frominner`,
  `frominner`, `frominner`, `frominner` and the empty string with `B` set. So compose takes the form
  under every operator this reader knows and at least three deep. The true reason is that a nested
  default is a second variable rather than a value, so `${A:-${B:-x}}` and `${A:-${C:-x}}` agree
  under a deployment setting neither and disagree under one that sets `B`. All three places now give
  that reason, recorded in [ADR-0063](../../adr/ADR-0063-compose-checks.md) decision 9, with the
  measurement in [compose interpolation](../../readings/compose-interpolation.md).
- 2026-09-15: the reading also found a defect in the message the refusal prints. `_braced` takes the
  body as the text up to the first `}`, so a nested variable is shown one brace short:
  `${A:-${B:-fallback}}` is reported as `nested substitution ${A:-${B:-fallback}`. Showing it whole
  needs a balanced scan, which is what reading the form needs too. The trigger has still not fired,
  over the same 78 variables.
- 2026-09-19: checked again, with the trigger restated and the account of the other readers
  repaired. The old trigger named an intention, and a nesting a change wanted could never reach the
  tree since the check refuses it; it now names a rename of a variable a compose file uses, which
  `git log` can answer, and none has happened since the two of 2026-08-30. The body said a nested
  reading would reach `bindcheck.py` and `volumecheck.py` as well as `defaultcheck.py`. It would
  not: `composedefaults.py` is read by `defaultcheck.py` for values and by `artifactnames.py` and
  `subagentservers.py` for names, and nothing else, while `bindcheck.py` reduces a bind source with
  its own pattern and raises `cannot reduce source '${A:-${B:-x}}/data' to a path`, and
  `composetargets.py` refuses any expansion in a short mount target. The same overstatement stood in
  the module's docstring and in [repo-checks.md](../../modules/repo-checks.md); both now name
  `defaultcheck.py` as the one rule that compares a default as a value.
- 2026-09-19: the message half was fixed apart from the form, recorded in
  [ADR-0063](../../adr/ADR-0063-compose-checks.md) decision 9. A scan that only builds the quotation
  widens nothing the check accepts, so the two were separated. The message now quotes the variable
  to the `}` that balances its opening, and to the first `}` when none does, and names a bare `{` in
  an argument as that rather than as a nesting. The form itself is still refused and still unread,
  so this entry stays open for it, and the balanced scan (`_spend_extent`) is there for a reading of
  the form to reuse. The same run showed all three compose checks counting the refused file as a
  finding of their own kind, and each failing run now prints the refused files under a summary of
  their own. Filed from the same measurement:
  [R-691](691-the-substitution-reader-refuses-a-brace-compose-reads-as-text.md).
