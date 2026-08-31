# Structural argument identity in salience

**Status:** declined 2026-07-16
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

This is the salience addendum's first remaining item. The
index warned that this very area had misdiagnosed its own cost before, so it was read against the
code first. The threat it carried, that permuted keys and other spellings evade a per-argument dedup,
is **already closed** for the case that motivated it: `RepeatSalience` compares `arguments` with
`Mapping.__eq__`, which is deep and key-order-independent at every nesting level, so permuted keys
already collapse to one call (`test_arguments_compare_structurally_rather_than_by_key_order` pins
it, and fails the moment identity switches to an unsorted serialization), JSON whitespace
never survives into the parsed mapping, and Python-equal scalars (`1` and `1.0`) collapse too. A
**schema-free** canonical form (recursively sort keys) closes nothing equality does not, and its
natural serialized shape is a regression: unsorted reopens permuted keys, sorted splits `1` from
`1.0`. The only cases a **schema** would close (a present-versus-omitted defaulted optional, a
cross-type scalar, and the entry's own `a.txt` versus `./a.txt`, which no schema reaches) are
unsound to fold: JSON Schema `default` is advisory, not applied, so folding an omitted key onto it
can collapse two calls a tool runs differently and **refuse a legitimate call**, the non-benign
failure this policy's "limit is two, not one" decision deliberately avoids. And the residual is
bounded anyway: extra dispatches are capped by `MAX_TOOL_DISPATCHES` (32) and `MAX_CALLS_PER_ROUND`
(16), and the card-spam case is bounded independently of spelling, since a gated call on a tainted
turn is denied outright with no card and an untainted turn's budget caps dispatches at 32. Docs
only, no seam change; the entry above stays verbatim as the historical record. It reopens only if
a real wired tool shows a semantic-equivalence evasion those three bounds do not cover, and even
then the sound fix is a per-tool domain normalizer (the model judgment the ADR rejected) rather than
schema folding. Nothing opened behind it.

## Trail

- 2026-07-16: Declined on the merits after being read against the code and recorded in the ADR-0009
  structural-identity addendum, the same terminal outcome the day's other reads against the code
  reached, this one turning on a fix that is a no-op at best and unsound at worst rather than on a
  missing consumer. The residual it leaves is bounded by `MAX_TOOL_DISPATCHES` (32),
  `MAX_CALLS_PER_ROUND` (16), and the tainted-turn denial, under which a gated call on a tainted
  turn gets no card whatever its spelling, so no spelling evasion becomes a flood or a breach.
