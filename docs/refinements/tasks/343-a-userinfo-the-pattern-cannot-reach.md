# A userinfo the pattern cannot reach

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a credential reaching a log line inside a URL the pattern does not match, most
plausibly a hand-written connection string in an env var whose password was never percent-encoded.
The env vars that could carry one are read off the compose files, `grep -rn "://" docker/*.yml`,
and each shape is read by putting the URL through `render_value` and then through each formatter
twice, as a field and as a message, which is five answers and not one. This entry's trail records
what the shipped URLs and each shape answered when that was last run.
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-12

`_USERINFO` is `(?<=://)[^/\s@]*@`, and it does not match three shapes of credential:

- a userinfo containing a `/`: `postgres://admin:hun/ter@db/x` is returned untouched, because the
  character class excludes the `/` that would otherwise let the match run into a path. This one
  reaches every line it can ride on, in both renderings;
- a userinfo containing the whitespace a JSON encoder leaves alone: `redis://:p w@redis:6379`
  likewise, `\s` being excluded for the same reason. This limb is narrower than it reads, and the
  reason is an interaction with escaping rather than anything in the pattern. Every value goes
  through `json.dumps` on its way to a line unless it is bare, and `_bound_value` runs the pattern
  over the escaped rendering, by which point a tab or a newline inside the userinfo is two printing
  characters and the pattern reaches it. So the whitespace that survives is the whitespace
  `json.dumps` does not escape: the space itself, and Unicode whitespace outside the C0 range such
  as U+00A0 and U+3000. A control character is exposed in exactly one place, the plain rendering's
  message and traceback, which no encoder touches;
- a credential with no scheme in front of it: `user:pw@host/x`, which the lookbehind refuses. That
  one is deliberate and is what leaves a bare email address alone, so it is listed for
  completeness rather than as a fault.

All three predate the per-value bound and are untouched by the cut-defeats-withholding addendum,
which fixed *when* the pattern runs and not *what* it matches. RFC 3986 requires both a `/` and a
space to be percent-encoded inside a userinfo, so a conforming URL is covered; the risk is a
connection string a person typed.

The fix is not obviously an improvement, which is why this is filed rather than done. Widening the
class to `[^\s@]*` trades under-redaction for over-redaction: `http://example.com/path@ref` would
lose its path, and `docker compose logs` is read by someone who needs those paths. Anchoring on
the scheme and matching to the last `@` before the first `/` of the path is closer to the grammar
but is a parser rather than a pattern, and the module's whole argument for a blunt denylist is
that a blunt rule erring toward withholding beats a clever one erring the other way. A third
option is to leave the shape alone and note that a credential this pattern misses is a credential
that was already outside the URL grammar.

## Trail

- 2026-09-12: trigger swept a third time and not fired, and the sweep found that the pattern is not
  the only thing standing between the one shipped credential and a log line. The five readings
  reproduce the 2026-09-08 table cell for cell, and the compose files are unchanged:
  `CORTEX_MEMORY_DSN` is still the only URL built with a credential and `CORTEX_PG_PASSWORD` still
  defaults to `cortex`. What is new is the path such a URL takes. No log call in the brain attaches
  either URL as a field: a grep over every `extra=` in the brain finds one endpoint field, the model
  host's, and that URL carries no credential. So a connection URL reaches a line only inside a
  library's exception text or a traceback, which is the one place this entry's table reports a
  control character exposed. Worse for the first limb, `asyncpg` misparses exactly the shape it is
  about: `create_pool("postgresql://cortex:hun/ter@postgres:5432/cortex")` raises `ValueError:
  invalid literal for int() with base 10: 'hun'`, which prints the password's first segment with no
  URL around it, so no shape rule here could withhold it; and that call is awaited with no `except`
  under a `__main__` that runs `asyncio.run` unguarded, so the traceback is printed by the
  interpreter and never passes through the formatter at all. Filed as
  [R-652](652-a-credential-can-leave-the-process-with-no-url-around-it.md). This entry is unchanged
  in substance: the three shapes stand, and widening the pattern would still not cover the shipped
  credential's own path.
- 2026-09-08: trigger swept and not fired, and the whitespace limb repaired above. The one URL this
  deployment builds with a credential in it is `CORTEX_MEMORY_DSN` in
  `docker/docker-compose.memory.yml`,
  `postgresql://cortex:${CORTEX_PG_PASSWORD:-cortex}@postgres:5432/cortex`, whose shipped password
  is `cortex` and carries neither a `/` nor a space; `CORTEX_REDIS_URL` ships without a credential
  at all. So the trigger fires on the day an operator sets `CORTEX_PG_PASSWORD` to something with a
  `/` or a space in it, and not before. Each shape was then put through the five readings today,
  reading whether `<redacted>` reaches the output: a `/` in the userinfo is exposed in all five; a
  space, a U+00A0 and a U+3000 are exposed in all five; a tab, a newline, a carriage return, a
  vertical tab and a form feed are withheld in a field value in both renderings and in the packed
  rendering's message, and exposed only in the plain rendering's message. A `"` or a `\` in the
  userinfo is withheld everywhere, the class admitting both. That escaping widens what the pattern
  reaches was the finding: it holds in every direction here, because JSON escaping only ever
  replaces a character the class excludes with characters it admits, and never the other way.
  Recorded in the ADR-0038 trigger-sweep addendum of the same day.
- 2026-08-20: Opened by the close of
  [R-324](324-a-rendered-field-has-no-bound.md)'s security follow-up, which fixed the order the
  withholding runs in and left what it matches exactly as it was.
