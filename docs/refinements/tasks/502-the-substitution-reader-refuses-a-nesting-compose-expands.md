# The substitution reader refuses a nesting compose expands

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a change wants a compose value that falls back through two variables, which is what an
env-var rename with a compatibility shim needs and what nothing in this tree needs today
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-30 by the close of
[R-492](492-the-embedder-names-its-artifact-outside-the-family.md), which wanted exactly this
shape for a rename's shim and measured that it was unavailable.

`scripts/composedefaults.py` raises `SubstitutionReadError` on a nested expansion, and until that
close its docstring gave the reason as "which compose does not expand". That is false:
`${A:-${B:-x}}` resolves to `B`'s value and then to `x` on compose v2.39.1, measured against the
real binary. The sentence is corrected, and the refusal is kept with the true reason written in
its place: every rule over these spends compares a default as a value, and a default that is
itself a variable has no value until a deployment supplies one, so a reader that returned
something for it would hand `defaultcheck.py`, `bindcheck.py` and `volumecheck.py` a comparison
none of them can make.

**Why it is worth reopening rather than settled.** The refusal is honest but it costs a shape
compose supports and this repo will want again. A two-variable fallback is the one cheap way to
rename an operator-facing compose variable without a deployment silently falling back to a shipped
default, which is the failure mode [AGENTS.md](../../../AGENTS.md) warns about for any key
something outside the repo depends on. The close that opened this entry took the rename without
the shim, on the argument that nothing off this machine reads that key; a key where that is not
true would need this, and would need it in the same commit as the rename.

**What would close it.** Teach `composedefaults.py` the nested form, and answer for each rule what
a nested default reduces to. Three shapes to weigh, cheapest first:

- **Read it and report the chain**, a `Substitution` whose argument is itself a list of
  substitutions with a literal at the end. Then each rule decides: `defaultcheck.py` compares the
  literal tail, which is what two files spelling the same chain must agree on; `bindcheck.py`
  resolves the tail as the path a `docker compose up` would land on with nothing set;
  `volumecheck.py` and `composetargets.py` do the same for a container path.
- **Read it and refuse to value it**, returning the spend so the name is visible to
  `artifactnames.py` and `subagentservers.py` while any rule asking for a value still raises. This
  is the smallest change that unblocks a rename shim, since those two readers want the variable
  name and never its default.
- **Keep refusing**, and say so as a decision rather than as a limit, which is where the sentence
  stands after the correction.

Note that the readers of a spend's *name* and the readers of its *value* are already different
callers, so the second shape is a real middle and not a fudge. Weigh also whether a chain longer
than two is worth reading at all, since compose allows it and no honest use of it exists here.

## Trail

- 2026-08-30: opened by the close of
  [R-492](492-the-embedder-names-its-artifact-outside-the-family.md), whose [ADR-0029
  addendum](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-30-a-non-chat-artifact-names-itself-in-the-family-and-the-exclusion-retires)
  records the measurement that falsified the docstring and the reason the shim was declined
  anyway.
