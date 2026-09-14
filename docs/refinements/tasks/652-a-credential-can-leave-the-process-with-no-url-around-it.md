# A credential can leave the process with no URL around it

**Status:** landed 2026-09-14
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-09-12 by the trigger sweep of
[R-343](343-a-userinfo-the-pattern-cannot-reach.md), which asks which credentials inside a URL the
withholding pattern misses and found one that never arrives inside a URL at all.

`redact_urls` withholds a credential by shape: `_USERINFO` matches what sits between a scheme's
`://` and an `@`. The one URL this deployment builds with a credential in it is `CORTEX_MEMORY_DSN`,
and the failure an unreadable one produces carries neither of those two anchors. Measured on
2026-09-12, `asyncpg.create_pool("postgresql://cortex:hun/ter@postgres:5432/cortex")` raises

```
ValueError: invalid literal for int() with base 10: 'hun'
```

because the `/` ends the authority for that parser and what follows the `:` is read as a port. The
password's first segment is the whole of the message, with no scheme and no `@` anywhere near it, so
no pattern over URL syntax can withhold it and widening the one in
[R-343](343-a-userinfo-the-pattern-cannot-reach.md) would not reach this.

**The second half is that the text never reaches the formatter.** `memory_builders` awaits
`PgVectorMemoryStore.connect(config.dsn)` with no `except` around it, and `__main__` runs
`asyncio.run(run_from_env())` with nothing guarding that, so a startup failure is printed by the
interpreter's own traceback hook to stderr. `logging` never sees it, which means neither
`PlainFormatter` nor the whole-line withholding runs, and the container log carries whatever the
exception said. Every URL-shaped credential in a startup traceback is exposed for that reason alone,
independently of what the pattern matches.

Three shapes are available and they cover different halves.

- **Refuse the DSN where it is read.** `MemoryConfig` already validates that a pgvector deployment
  names both a DSN and an embedder, so a second validator could refuse a DSN whose userinfo carries
  a character this parser misreads, naming the variable and never the value. That covers the
  measured leak at its source and costs one rule that has to keep agreeing with a library's parser.
- **Log the entry's fatal error rather than letting the interpreter print it.** A guard around
  `asyncio.run` that logs the exception routes every startup traceback through the formatter, which
  withholds every URL-shaped credential in it. It does nothing for the message above, whose text
  carries no URL, and it changes what a crashed container's last line looks like.
- **Require the password percent-encoded and say so.** RFC 3986 already requires it, the memory
  runbook does not, and a documented requirement is not a defence.

What is not settled is whether the first is worth writing before anything has bitten, since the
shipped password is `cortex` and the leak needs an operator to choose a password the parser cannot
read. The reading itself is worth having: the withholding this repo argued at length is a rule over
URL syntax, and a credential can leave the process outside that syntax entirely.

## Trail

- 2026-09-14: landed as the first of the three shapes. `MemoryConfig` carries a second
  `model_validator` refusing a DSN whose authority the Postgres driver cannot read
  (`authority_is_readable`, `brain/packages/orchestrator/src/cortex_orchestrator/dsn.py`, which
  reruns three of `asyncpg`'s own parsing steps), and both of that class's validators now raise
  `MemoryConfigError` rather than `ValueError`: Pydantic renders the validated input beside a
  converted message, so the entry's own proposal of a validator naming the variable and never the
  value would have printed the credential anyway. The second shape, routing a startup traceback
  through the formatter, is filed as
  [R-664](664-a-startup-traceback-reaches-stderr-with-no-formatter.md); the third, documenting
  RFC 3986's requirement, is declined as a requirement rather than a defence. The reasoning, the
  Pydantic rendering and the mutation table are in the ADR-0038 unreadable-DSN addendum, and the
  reading to retake after a driver upgrade is in the memory runbook.
- 2026-09-14: trigger swept and not fired, and both halves re-derived. `grep -rn "PG_PASSWORD"
  docker/` still finds `CORTEX_PG_PASSWORD` only in `docker/docker-compose.memory.yml`, defaulting
  to `cortex` in all three places that spell it, the DSN, the Postgres server's own
  `POSTGRES_PASSWORD` and the backup job's `PGPASSWORD`, and that default carries no `/`. On
  `asyncpg` 0.31.0 today, `create_pool("postgresql://cortex:hun/ter@postgres:5432/cortex")` raises
  the same `ValueError: invalid literal for int() with base 10: 'hun'` recorded above, and a
  password of `pw/5432` raises the same error naming `pw`, so what reaches the message is the
  segment in front of the `/` and nothing about the word itself. The three other shapes answer as
  before in substance: an unknown scheme is refused naming the scheme alone, and a password carrying
  a space or an `@` names no part of itself, though run outside the compose network those two fail
  at name resolution rather than by timing out, `postgres` resolving nowhere here. The second half
  is unchanged in the code: `memory_builders.py` still awaits
  `PgVectorMemoryStore.connect(config.dsn)` with no `except` around it, `__main__.py` still runs
  `asyncio.run(run_from_env())` under a bare entry guard, and `MemoryConfig`'s one validator still
  checks only that a pgvector deployment names both a DSN and an embedder. So a startup failure is
  still printed by the interpreter rather than through the formatter.
- 2026-09-12: opened by the trigger sweep of
  [R-343](343-a-userinfo-the-pattern-cannot-reach.md). `CORTEX_PG_PASSWORD` still defaults to
  `cortex` in `docker/docker-compose.memory.yml` and carries no `/`, so the trigger has not fired.
  Four DSN shapes were put through `asyncpg.create_pool`: a password carrying a `/` names its first
  segment in a `ValueError` and a password carrying a space does not, the connection timing out
  instead; an unknown scheme is refused naming the scheme alone. A grep over every `extra=` in the
  brain confirms no log call attaches either connection URL as a field, so an exception's text and a
  traceback are the only paths one takes to a line.
