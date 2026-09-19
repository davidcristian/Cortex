# A credential can leave the process with no URL around it

**Status:** done 2026-09-14
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`redact_urls` withholds a credential by shape: `_USERINFO` matches what sits between a scheme's
`://` and an `@`. The one URL this deployment builds with a credential in it is `CORTEX_MEMORY_DSN`,
and the failure an unreadable one produces has neither anchor. Measured on 2026-09-12,
`asyncpg.create_pool("postgresql://cortex:hun/ter@postgres:5432/cortex")` raises

```
ValueError: invalid literal for int() with base 10: 'hun'
```

because the `/` ends the authority for that parser and what follows the `:` is read as a port. The
password's first segment is the whole of the message, with no scheme and no `@` anywhere near it, so
no pattern over URL syntax can withhold it, and widening the one in
[R-343](343-a-userinfo-the-pattern-cannot-reach.md) would not reach this.

**The second half is that the text never reaches the formatter.** `memory_builders` awaits
`PgVectorMemoryStore.connect(config.dsn)` with no `except` around it, and `__main__` runs
`asyncio.run(run_from_env())` with nothing guarding that, so a startup failure is printed by the
interpreter's own traceback hook to stderr. `logging` never sees it, so neither `PlainFormatter` nor
the whole-line withholding runs. Every URL-shaped credential in a startup traceback is exposed for
that reason alone, whatever the pattern matches.

Three options were weighed. Refusing the DSN where it is read covers the measured leak at its
source and costs one rule that has to keep agreeing with a library's parser. Logging the entry
point's fatal error rather than letting the interpreter print it routes every startup traceback
through the formatter, but does nothing for the message above, whose text has no URL. Requiring the
password percent-encoded, which RFC 3986 already does, is a requirement rather than a defence.

**What closed it.** `MemoryConfig` gained a second `model_validator` refusing a DSN whose authority
the Postgres driver cannot read (`authority_is_readable`,
`brain/packages/orchestrator/src/cortex_orchestrator/dsn.py`, which repeats three of `asyncpg`'s own
parsing steps), and both of that class's validators now raise `MemoryConfigError` rather than
`ValueError`: Pydantic renders the validated input beside a converted message, so a validator naming
the variable and never the value would have printed the credential anyway. The second option is
filed as [R-664](664-a-startup-traceback-reaches-stderr-with-no-formatter.md); the third is
declined. The decision is ADR-0051 decision 11, and the reading to take again after a driver upgrade
is in the memory runbook.

## History

- 2026-09-12: opened by the trigger review of
  [R-343](343-a-userinfo-the-pattern-cannot-reach.md), which asks which credentials inside a URL the
  withholding pattern misses and found one that never arrives inside a URL at all.
  `CORTEX_PG_PASSWORD` still defaults to `cortex` in `docker/docker-compose.memory.yml` and has no
  `/`, so the trigger has not fired. Four DSN forms were put through `asyncpg.create_pool`: a
  password with a `/` names its first segment in a `ValueError` and a password with a space does
  not, the connection timing out instead; an unknown scheme is refused naming the scheme alone. A
  grep over every `extra=` in the brain confirms no log call attaches either connection URL as a
  field, so an exception's text and a traceback are the only routes one takes to a line.
- 2026-09-14: trigger reviewed, not fired, and both halves checked again.
  `grep -rn "PG_PASSWORD" docker/` still finds `CORTEX_PG_PASSWORD` only in
  `docker/docker-compose.memory.yml`, defaulting to `cortex` in all three places that use it, the
  DSN, the Postgres server's own `POSTGRES_PASSWORD` and the backup job's `PGPASSWORD`. On `asyncpg`
  0.31.0 today, `create_pool("postgresql://cortex:hun/ter@postgres:5432/cortex")` raises the same
  `ValueError` recorded above, and a password of `pw/5432` raises the same error naming `pw`, so
  what reaches the message is the segment in front of the `/`. The other forms answer as before,
  though run outside the compose network the two that named no part of themselves fail at name
  resolution rather than by timing out, `postgres` resolving nowhere here. The second half is
  unchanged in the code: `memory_builders.py` still awaits `PgVectorMemoryStore.connect(config.dsn)`
  with no `except` around it, `__main__.py` still runs `asyncio.run(run_from_env())` under a bare
  entry guard, and `MemoryConfig`'s one validator still checks only that a pgvector deployment names
  both a DSN and an embedder.
- 2026-09-14: done, as the first of the three options.
