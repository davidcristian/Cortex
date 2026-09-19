# Readings: how compose interpolates a file

What Docker Compose substitutes and where, read with `docker compose config`, which renders a
file without pulling an image or starting anything. Cited by
[ADR-0063](../adr/ADR-0063-compose-checks.md), decisions 8 and 9.

## Comments and block scalars

**2026-08-23**, compose v2.39.1. A file whose live value uses an unset `${CORTEX_TEST_UNSET:?...}`
is refused, and the refusal names `services.a.command.[]`, a path into the parsed document. The same
text written as a whole-line comment, and as a trailing comment after a value, is accepted. A `>-`
block scalar using an unset variable on its second line is refused, naming
`services.a.environment.NOTE`. So interpolation runs over the strings a YAML parse produced: a
comment is never substituted, and a block scalar's content is.

## Nested defaults

**2026-09-15**, compose v2.39.1, a scratch compose file.

| Expression | Nothing set | `B=frominner` | `A=fromouter` |
| --- | --- | --- | --- |
| `${A:-${B:-fallback}}` | `fallback` | `frominner` | `fromouter` |
| `${A:-${B:-${C:-deep}}}` | `deep` | `frominner` | `fromouter` |
| `${A-${B-bare}}` | `bare` | `frominner` | `fromouter` |
| `${A:-${B}}` | empty string | `frominner` | `fromouter` |
| `${A:+${B:-rep}}` | empty string | empty string | `rep` |

## Where an expression containing a brace ends

**2026-09-19**, compose v2.39.1, a scratch compose file.

| Expression | Nothing set | `A=outer` | `B=inner` |
| --- | --- | --- | --- |
| `${A:-${B:-x}}tail` | `xtail` | `outertail` | `innertail` |
| `${A:-{x}}tail` | `{x}tail` | `outertail` | `{x}tail` |
| `${A:-{x}` | `{x` | `outer` | `{x` |
| `${A:-${B:-{y}}}tail` | `{y}tail` | not taken | `innertail` |
| `${A:-${B}` | refused: `invalid interpolation format` | refused | not taken |

Compose ends such an expression at the `}` that balances its opening, counting a bare `{` as well as
a `${`. With none balancing it, `${A:-{x}` ends at the first `}` and `${A:-${B}` is refused.

Method: `docker compose -f <scratch>.yml config` with each variable set or unset in the calling
environment; the reader's handling of each form is asserted in
`scripts/tests/test_composedefaults.py`.
