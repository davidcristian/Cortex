# The substitution reader refuses a nesting compose expands

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a commit after 2026-08-30 renames a variable a compose file under `docker/` spends,
which is the change a two-variable fallback exists to shim. Checkable with
`git log -p -- 'docker/*.yml'`, reading for a spend name one commit removes while adding another;
the embedder's and the projector's model-file renames of 2026-08-30 are the only two so far, both
taken without a shim
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)
**Verified:** 2026-09-19

Opened 2026-08-30 by the close of
[R-492](492-the-embedder-names-its-artifact-outside-the-family.md), which wanted exactly this
shape for a rename's shim and measured that it was unavailable.

`scripts/composedefaults.py` raises `SubstitutionReadError` on a nested expansion, and until that
close its docstring gave the reason as "which compose does not expand". That is false:
`${A:-${B:-x}}` resolves to `B`'s value and then to `x` on compose v2.39.1, measured against the
real binary. The docstring is corrected, and the refusal is kept with the true reason written in
its place: the one rule reading a spend's value through this module, `defaultcheck.py`, compares a
default as a value, and a nested default is a second spend rather than a value, standing for one
thing with nothing set and another once the inner variable is set, so a reader that returned
either reading would hand that rule a comparison it cannot make. `bindcheck.py` and
`volumecheck.py` do not read spends through this module at all: `bindcheck.py` reduces a bind
source with a pattern of its own, which leaves the outer spend of a nesting unreduced and fails
with `cannot reduce source`, and `composetargets.py` refuses any expansion in a short mount's
target.

**Why it is worth reopening rather than settled.** The refusal is honest but it costs a shape
compose supports and this repo will want again. A two-variable fallback is the one cheap way to
rename an operator-facing compose variable without a deployment silently falling back to a shipped
default, which is the failure mode [AGENTS.md](../../../AGENTS.md) warns about for any key
something outside the repo depends on. The close that opened this entry took the rename without
the shim, on the argument that nothing off this machine reads that key; a key where that is not
true would need this, and would need it in the same commit as the rename.

**What would close it.** Make `composedefaults.py` read the nested form, and answer for each rule what
a nested default reduces to. Three shapes to weigh, cheapest first:

- **Read it and report the chain**, a `Substitution` whose argument is itself a list of
  substitutions with a literal at the end. Then the rules diverge: `defaultcheck.py` compares the
  literal tail, which is what two files spelling the same chain must agree on. A nested bind
  source or mount target would stay refused, since `bindcheck.py` and `composetargets.py` read
  those with their own patterns, and teaching them the tail is a second change in each.
- **Read it and report no value**, returning the spend so the name is visible to
  `artifactnames.py` and `subagentservers.py` while any rule asking for a value still raises. This
  is the smallest change that unblocks a rename shim, since those two readers want the variable
  name and never its default.
- **Keep raising on it**, and say so as a decision rather than as a limit, which is where the
  sentence stands after the correction.

Note that the readers of a spend's *name* and the readers of its *value* are already different
callers, so the second shape is a real middle and not a fudge. Weigh also whether a chain longer
than two is worth reading at all, since compose allows it and no honest use of it exists here.

## Trail

- 2026-08-30: opened by the close of
  [R-492](492-the-embedder-names-its-artifact-outside-the-family.md), whose [ADR-0029
  addendum](../../adr/ADR-0029-vision-screen-capture.md)
  records the measurement that falsified the docstring and the reason the shim was declined
  anyway.
- 2026-09-09: claims re-derived, and the correction the entry reports had reached one of three
  places. `composedefaults.py` still refuses a nesting, and its docstring carries the true reason,
  but the message it raises still ended `which compose does not expand`, and so did the sentence
  describing the refusal in [repo-gates.md](../../modules/repo-gates.md). Both are corrected here,
  so the reason an operator reads on a fault now matches the reason the module gives. The
  measurement is re-taken against the same binary rather than quoted: on Docker Compose v2.39.1,
  `docker compose config` over `OUT: "${A:-${B:-fallback}}"` prints `OUT: fallback` with neither
  set, `OUT: frominner` with `B` set, and `OUT: fromouter` with `A` set. The suite pins only the
  words `nested substitution`, so the tail was free to move. The trigger has not fired: no compose
  file in `docker/` spells a nested substitution, over 76 spends read.
- 2026-09-14: still not fired, and the correction the last reading landed is the state of the
  tree. `composedefaults._braced` raises on a body carrying a `{`, and the message it raises now
  ends `whose default is itself a variable and so has no value for a rule over these spends to
  compare`, which is the reason [repo-gates.md](../../modules/repo-gates.md) gives as well. No
  compose file in `docker/` spells a nested substitution, over 78 spends read across the ten
  files, two more than the 76 the last reading counted. The three shapes this entry weighs are
  unchanged, and so is the argument for the middle one: `artifactnames.py` and
  `subagentservers.py` read a spend's name and never its default, so a reader that returned the
  name and refused the value would unblock a rename shim without handing `defaultcheck.py`,
  `bindcheck.py` or `volumecheck.py` a comparison none of them can make.
- 2026-09-15: the reason the last reading landed is itself false, and the measurement falsifying
  it was already one bullet above it. That reading wrote that a nested default "has no value until
  a deployment supplies one", into the docstring, the message an operator reads on a fault and
  [repo-gates.md](../../modules/repo-gates.md), while the 2026-09-09 bullet records
  `${A:-${B:-fallback}}` printing `fallback` with neither variable set. It has a value with
  nothing set. The measurement is re-taken and widened here, over a scratch compose file read with
  `docker compose config` on v2.39.1: `${A:-${B:-fallback}}`, `${A:-${B:-${C:-deep}}}`,
  `${A-${B-bare}}`, `${A:-${B}}` and `${A:+${B:-rep}}` print `fallback`, `deep`, `bare`, the empty
  string and the empty string with nothing set, and `frominner`, `frominner`, `frominner`,
  `frominner` and the empty string with `B` set. So compose takes the form under every operator
  this reader knows and at least three deep, and each spend reduces to a value with nothing set.
  The true reason is what the readings with `B` set show: a nested default is a second spend rather than
  a value, so `${A:-${B:-x}}` and `${A:-${C:-x}}` agree under a deployment setting neither and
  disagree under one that sets `B`, where `defaultcheck.py` compares a default as one value. All
  three places now carry that reason, recorded in the [ADR-0026 addendum on what a nested compose
  default stands for](../../adr/ADR-0026-prose-style-gates.md).
  Nothing the gate accepts or refuses moved.
- 2026-09-15: the reading also found a defect in the fault the refusal prints, which belongs to
  this entry because it needs the same scan reading the form would. `_braced` takes the body as
  the text up to the first `}`, so a nested spend is shown one brace short:
  `${A:-${B:-fallback}}` is reported as `nested substitution ${A:-${B:-fallback}`, a spend the
  file does not contain. Showing it whole needs a balanced scan, which is what reading the form
  needs too, so it lands with the form or not at all. The trigger has still not fired: no compose
  file in `docker/` spells a nested substitution, over 78 spends read across the ten files, the
  same count as the last reading.
- 2026-09-19: re-derived, with the trigger restated and the account of the other readers repaired.
  The trigger did not fire and could not have: "a change wants" a fallback names an intention, and
  a nesting a change wanted could never reach the tree, since the gate refuses it. It now names the
  change that wants the shim, a rename of a variable a compose file spends, which `git log` over
  `docker/` can answer; none has happened since the two of 2026-08-30. The body said a nested
  reading would reach `bindcheck.py` and `volumecheck.py` as well as `defaultcheck.py`. It would
  not: `composedefaults.py` is read by `defaultcheck.py` for values and by `artifactnames.py` and
  `subagentservers.py` for names, and nothing else, while `bindcheck.py` reduces a bind source with
  its own pattern and raises `cannot reduce source '${A:-${B:-x}}/data' to a path` on a nesting,
  measured today, and `composetargets.py` refuses any expansion in a short mount target. The same
  overstatement stood in the module's docstring and in
  [repo-gates.md](../../modules/repo-gates.md), which said every rule over these spends compares a
  default as a value; both now name `defaultcheck.py` as the one that does. No compose file
  spells a nesting, over the same 78 spends across ten files.
- 2026-09-19: the message half landed apart from the form, recorded in the [ADR-0026 addendum on
  quoting a nested spend
  whole](../../adr/ADR-0026-prose-style-gates.md).
  The 2026-09-15 bullet tied the one-brace-short fault to reading the form; a scan that only builds
  the quotation widens nothing the gate accepts, so the two were separated. Re-measured first,
  `defaultcheck.py --root` over a scratch file printed `nested substitution ${A:-${B:-x}`. The
  fault now quotes the spend to the `}` that balances its opening, which is where compose ends it,
  and to the first `}` when none does, and names a bare `{` in an argument as that rather than as
  a nesting. The form itself is still refused and still unread, so this entry stays open for it,
  and the balanced scan (`_spend_extent`) is there for a reading of the form to reuse. The same
  run showed `defaultcheck.py`'s summary counting the refused file as a variable, and a failing
  run now prints one summary per kind of fault, refused files apart from disagreeing variables.
  Two neighbours were filed from the same measurement:
  [R-691](691-the-substitution-reader-refuses-a-brace-compose-reads-as-text.md) and
  [R-693](693-the-bind-and-volume-gates-count-a-file-they-could-not-read-as-a-finding.md).
