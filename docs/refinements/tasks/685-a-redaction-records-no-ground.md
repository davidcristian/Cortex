# A redaction records no ground an operator can count

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Verified:** 2026-09-17

`_UrlRedactingFilter._redacted` (`brain/packages/core/src/cortex_core/guardrail.py:222`) replaces a
flagged URL with `REDACTED_LINK` whichever ground flagged it: a URL collected from an untrusted
result, the `strict` ground that takes every URL the user did not send, or the lookalike ground that
takes a non-ASCII host. `guardrail.py` holds no logger, so the only trace a redaction leaves is that
same marker in the persisted reply, which says a link was removed and never why.

That makes the measurement [R-284](284-the-lookalike-policy-as-the-shipped-default.md) waits on
impossible to take. A week under `CORTEX_OUTPUT_GUARDRAIL=lookalike` would yield a count of removed
links and no count of the ones only the lookalike ground removed, which is the false-positive
number the default question turns on.

**What would be built.** `_flagged` returns the ground that decided, the filter keeps a count per
ground for the turn, and the turn logs one line when the reply is settled carrying those counts and
the policy name, never a URL or a host, since the host is the untrusted content. A turn with no
redaction logs nothing. The new line joins the pinned occurrences in `scripts/logcouplings.py` and
the runbook sample `samplecheck.py` holds, and a test drives one reply that each ground flags. The
code is in `brain/packages/core/`, which was reserved for a running measurement on the day this was
filed.

## Trail

- 2026-09-17: filed by the trigger sweep over
  [R-284](284-the-lookalike-policy-as-the-shipped-default.md), which found its measurement had no
  instrument. Recorded in the ADR-0015 addendum of 2026-09-17.
