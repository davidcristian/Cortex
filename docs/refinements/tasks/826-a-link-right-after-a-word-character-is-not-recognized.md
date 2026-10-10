# A link right after a word character is not recognized

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)
**Verified:** 2026-10-10

`URL_RE` in `brain/packages/core/src/cortex_core/urls.py` opens with `\b`, so a scheme preceded by
a letter, a digit or an underscore is never matched. The overlay draws a reply as plain text, so a
model that writes a collected link in underscore emphasis shows it whole:

```
extract_urls("open _https://evil.example/report_ now")  # frozenset()
extract_urls("x_https://evil.example/report")           # frozenset()
```

A guard holding `https://evil.example/report` as collected passes `_https://evil.example/report_`
unchanged under every policy, on the reply and on the thinking status. Found on the Linux shell
([readings](../../readings/overlay-email-flows.md#a-message-holding-an-injection-and-two-links)),
where the fix for a closing backtick, asterisk or tilde went in; underscore was left out of that
fix because no closing delimiter matters while the opening one stops the match.

## What to do

Replace the leading `\b` with a lookbehind that refuses only a letter or digit, or admits an
underscore before a listed scheme, and run the whole guardrail suite: the streaming hold in
`url_holdback.py` and the `held_from` reading both assume where a match can start. Then add `_` to
`TRAILING_PUNCTUATION`, with a test for `_link_` on both channels and a mutation row each.

## History

- 2026-10-10: filed from the email flows on the Linux shell.
