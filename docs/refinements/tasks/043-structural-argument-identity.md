# Structural argument identity in salience

**Status:** declined 2026-07-16
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The worry was that permuted keys and other ways of writing the same arguments evade the
per-argument duplicate check. Read against the code, it is already closed for the case that
motivated it: `RepeatSalience` compares `arguments` with `Mapping.__eq__`, which is deep and
independent of key order at every level of nesting, so permuted keys already collapse to one call.
`test_arguments_compare_structurally_rather_than_by_key_order` asserts that and fails the moment
identity switches to an unsorted serialization. JSON whitespace never survives into the parsed
mapping, and scalars Python considers equal (`1` and `1.0`) collapse too.

A canonical form without a schema, recursively sorting keys, closes nothing equality does not, and
its natural serialized form is worse: unsorted reopens permuted keys, sorted splits `1` from
`1.0`. The only cases a schema would close are a present versus omitted optional with a default, a
cross-type scalar, and `a.txt` versus `./a.txt`, which no schema reaches. Folding them is unsound:
JSON Schema `default` is advisory and not applied, so folding an omitted key onto it can collapse
two calls a tool runs differently and refuse a legitimate call, which is the harmful failure the
"limit is two, not one" decision deliberately avoids.

The residue is bounded anyway. Extra dispatches are capped by `MAX_TOOL_DISPATCHES` (32) and
`MAX_CALLS_PER_ROUND` (16), and the card spam is bounded independently of how the arguments are
written, since a call needing confirmation on a tainted turn is denied outright with no card and
an untainted turn's budget caps dispatches at 32. Documentation only, no port change. It reopens
only if a real wired tool shows an evasion those three bounds do not cover, and even then the
sound fix is a per-tool normalizer, which is the model judgement the ADR rejected, rather than
schema folding.

## History

- 2026-07-16: Declined on the merits after being read against the code and recorded in ADR-0009
  decision 12. It turns on a fix that is a no-op at best and unsound at worst rather than on a
  missing consumer. The residue it leaves is bounded by `MAX_TOOL_DISPATCHES` (32),
  `MAX_CALLS_PER_ROUND` (16) and the tainted-turn denial, under which a call needing confirmation
  on a tainted turn gets no card however its arguments are written.
