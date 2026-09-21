# The credential pattern misses three kinds of URL

**Status:** open, waiting for its trigger
**Area:** cross-cutting
**Trigger:** a credential reaching a log line inside a URL the pattern does not match, most likely
a hand-written connection string in an environment variable whose password was never
percent-encoded. The variables that could contain one are read off the compose files,
`grep -rn "://" docker/*.yml`, and each form is checked by putting the URL through `render_value`,
through each formatter twice, as a field and as a message, and through the tool audit file's
`durable_value`, which is six results and not one. The history below records what the shipped URLs
and each form answered when that was last run.
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-09-19

`_USERINFO` is `(?<=://)[^/\s@]*@`, and it does not match three kinds of credential:

- a userinfo containing a `/`: `postgres://admin:hun/ter@db/x` is returned untouched, because the
  character class excludes the `/` that would otherwise let the match run into a path. This reaches
  every line it can go on, in both renderings.
- a userinfo containing whitespace a JSON encoder leaves alone: `redis://:p w@redis:6379` likewise,
  `\s` being excluded for the same reason. This is narrower than it reads, because of escaping
  rather than the pattern. Every value goes through `json.dumps` on its way to a line unless it is
  bare, and `_bound_value` runs the pattern over the escaped rendering, by which point a tab or a
  newline inside the userinfo is two printing characters and the pattern reaches it. So what
  survives is the whitespace `json.dumps` does not escape: the space itself, and Unicode whitespace
  outside the C0 range such as U+00A0 and U+3000. A control character is exposed in exactly one
  place, the plain rendering's message and traceback, which no encoder touches.
- a credential with no scheme in front of it: `user:pw@host/x`, which the lookbehind refuses. That
  one is deliberate and is what leaves a bare email address alone.

All three predate the per-value bound and are untouched by the change that made the cut defeat
withholding, which fixed when the pattern runs and not what it matches. RFC 3986 requires both a `/`
and a space to be percent-encoded inside a userinfo, so a conforming URL is covered; the risk is a
connection string a person typed.

The fix is not obviously an improvement. Widening the class to `[^\s@]*` trades under-redaction for
over-redaction: `http://example.com/path@ref` would lose its path, and `docker compose logs` is
read by someone who needs those paths. Anchoring on the scheme and matching to the last `@` before
the first `/` of the path is closer to the grammar but is a parser rather than a pattern, and the
module's argument for a blunt list of withheld names is that a blunt rule erring toward withholding
beats a clever one erring the other way. A third option is to leave it alone and record that a
credential this pattern misses was already outside the URL grammar.

## History

- 2026-08-20: Opened by the security follow-up to
  [R-324](324-a-rendered-field-has-no-bound.md), which fixed the order the withholding runs in and
  left what it matches exactly as it was.
- 2026-09-08: Trigger checked and not fired, and the whitespace point above repaired. The one URL
  this deployment builds with a credential in it is `CORTEX_MEMORY_DSN` in
  `docker/docker-compose.memory.yml`,
  `postgresql://cortex:${CORTEX_PG_PASSWORD:-cortex}@postgres:5432/cortex`, whose shipped password
  is `cortex` and has neither a `/` nor a space; `CORTEX_REDIS_URL` ships without a credential at
  all. So the trigger fires the day an operator sets `CORTEX_PG_PASSWORD` to something with a `/`
  or a space in it. Each form was put through the five readings today: a `/` in the userinfo is
  exposed in all five; a space, a U+00A0 and a U+3000 are exposed in all five; a tab, a newline, a
  carriage return, a vertical tab and a form feed are withheld in a field value in both renderings
  and in the packed rendering's message, and exposed only in the plain rendering's message; a `"`
  or a `\` is withheld everywhere. Escaping widens what the pattern reaches in every direction
  here, because JSON escaping only ever replaces a character the class excludes with characters it
  admits.
- 2026-09-12: Trigger checked a third time and not fired, and the pattern is not the only thing
  between the one shipped credential and a log line. The five readings reproduce the 2026-09-08
  results exactly, and the compose files are unchanged. What is new is the path such a URL takes.
  No log call in the brain attaches either URL as a field: a grep over every `extra=` in the brain
  finds one endpoint field, the model host's, and that URL has no credential. So a connection URL
  reaches a line only inside a library's exception text or a traceback, which is the one place a
  control character is exposed. Worse, `asyncpg` misparses exactly the shape this is about:
  `create_pool("postgresql://cortex:hun/ter@postgres:5432/cortex")` raises `ValueError: invalid
  literal for int() with base 10: 'hun'`, which prints the password's first segment with no URL
  around it, so no rule here could withhold it; and that call is awaited with no `except` under a
  `__main__` that runs `asyncio.run` unguarded, so the traceback is printed by the interpreter and
  never passes through the formatter. Filed as
  [R-652](652-a-credential-can-leave-the-process-with-no-url-around-it.md).
- 2026-09-14: Trigger checked a fourth time and not fired, and the five readings reproduce again,
  cell for cell. The compose files are unchanged: `CORTEX_MEMORY_DSN` is still the only URL built
  with a credential and `CORTEX_PG_PASSWORD` still defaults to `cortex`. One count has grown
  without changing the conclusion: the grep for a URL among the brain's `extra=` dicts finds six
  call sites today rather than one, five attaching a URL (two in `cortex_inference/trace_probe.py`,
  two in `cortex_orchestrator/vision.py`, one in `cortex_model_manager/probe.py`) and one attaching
  a bare host and port. None of the six can contain a credential.
- 2026-09-15: Trigger checked a fifth time and not fired, and the thirteen forms were put through
  the five readings again rather than reasoned about. Every result reproduces, and the compose
  files are unchanged. The entry has now reproduced identically four times running, which makes it
  a description of a pattern nobody has changed rather than an open question about the tree.
- 2026-09-19: Trigger checked a sixth time and not fired, and the readings are six now. `_USERINFO`
  in `cortex_core/log_fields.py` is unchanged, and `CORTEX_MEMORY_DSN` is still the only URL the
  compose files build with a credential. Since 2026-09-17 a URL a model writes into a tool argument
  also reaches the audit file when `CORTEX_TOOLS_AUDIT_FILE` is set, and `durable_value` is a sixth
  reading of it. Eight of the thirteen forms were run today: a `/`, a space, a U+00A0, a tab, a
  newline, a `"`, a credential with no scheme and the shipped DSN. The five old readings reproduce
  for all eight, and the file reads exactly as a field does, a tab or a newline included, because
  `durable_value` withholds credentials string by string, compares the result with the line's own
  rendering, and keeps the rendering whenever the two differ. The carriage return, the vertical
  tab, the form feed, the U+3000 and the `\` were not run. The path the 2026-09-12 entry found was
  read the same day under
  [R-664](664-a-startup-traceback-reaches-stderr-with-no-formatter.md): with a DSN whose host does
  not resolve, the boot ended in a raw traceback that contained no fragment of the password.
