# A userinfo the pattern cannot reach

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a credential reaching a log line inside a URL the pattern does not match, most
plausibly a hand-written connection string in an env var whose password was never percent-encoded
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`_USERINFO` is `(?<=://)[^/\s@]*@`, and three shapes of credential walk past it:

- a userinfo containing a `/`: `postgres://admin:hun/ter@db/x` is returned untouched, because the
  character class excludes the `/` that would otherwise let the match run into a path;
- a userinfo containing whitespace: `redis://:p w@redis:6379` likewise, `\s` being excluded for
  the same reason;
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

- 2026-08-20: Opened by the close of
  [R-324](324-a-rendered-field-has-no-bound.md)'s security follow-up, which fixed the order the
  withholding runs in and left what it matches exactly as it was.
