# A registered binding handed at a wrapped call has no one-line search text

**Status:** done 2026-09-15
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

The test checks that the registry entry's search text falls on the line the name sits on, which
`logcalls.handed` reports as the name's own line rather than the call's. On the one site registered
today those are one line. Four of the brain's twelve handed calls are wrapped by the formatter, the
abandonment warning, the no-reading line, the unreadable-call warning and the short-card error, each
with the identifier on the line after the opening parenthesis, and on any of the four the template
the failure message suggested until 2026-09-15, `<the call>({name},`, renders a search text the file
does not contain, since a newline and an indent stand between the parenthesis and the name.

Two forms work and neither was written down. `{name},` alone falls on the name's line and is bounded
at the word edge, and it is looser: it matches wherever the identifier is followed by a comma, an
`__all__` list among them, and only the line check connects it to the call. A template containing
the line break and the indent locks the call and is broken by any reformat that moves the wrap.

## History

- 2026-09-02: opened by the close of
  [R-504](504-a-declared-message-and-a-different-word-in-the-call.md), whose mutation table measures
  a one-line call handed another word and says nothing about a wrapped one.
- 2026-09-04: checked and left open. The brain hands its message by name at eleven log calls, five
  of them a binding the module makes at its own top level (`_NO_READING_LOG_MSG`, `SPILLED_LOG_MSG`
  and `_MEASURED_LOG_MSG` in `cortex_core/brain_phase.py`, `ABANDONED_MESSAGE` in
  `cortex_orchestrator/abandon.py`, `_MESSAGE` in `cortex_tools/audit.py`) and the other six a local
  `msg` built in the function. Two of the five are wrapped and neither is registered: the test's own
  reading over the real registry returns one row, the audit sink's `_MESSAGE` at `audit.py:89`,
  whose call is on one line. Rendering the suggested template against the two wrapped calls confirms
  the miss: `_logger.warning(ABANDONED_MESSAGE,` and `_logger.info(_NO_READING_LOG_MSG,` are each
  found zero times in their own file, where `_logger.info(_MESSAGE,` is found once.
- 2026-09-07: checked again and left open. `logcalls.handed` reports 11 brain log calls whose
  message is a bare name; five of those names are bound at their module's own top level, at the same
  lines (`_NO_READING_LOG_MSG` at `brain_phase.py:191`, `SPILLED_LOG_MSG` at 210, `_MEASURED_LOG_MSG`
  at 212, `ABANDONED_MESSAGE` at `abandon.py:73`, `_MESSAGE` at `audit.py:89`); and comparing each
  name's line with its call's still marks two of them wrapped. Neither has gained a `Site`.
- 2026-09-13: checked again and corrected. `logcalls.handed` still reports 11 brain log calls whose
  message is a bare name, and all 11 names are now bound at their module's own top level, where five
  were: the six that were a local `msg` are now `_NO_DEVICE_MEMORY` and `_CARD_TOO_SHORT` in
  `cortex_core/residency_moves.py`, `_NOT_CONVERGED` and `_WORST_STOP_UNCLEARED` in
  `cortex_core/residency_watch.py`, and a `_REFUSED` in each of `cortex_orchestrator/bounds.py` and
  `cortex_orchestrator/swap_builders.py`. Comparing each name's line with its call's marks three of
  them wrapped rather than two: `_NO_READING_LOG_MSG` at `brain_phase.py:191`, `ABANDONED_MESSAGE`
  at `abandon.py:73`, and `_CARD_TOO_SHORT` at `residency_moves.py:161`. None has gained a `Site`.
- 2026-09-15: closed as the shorter of the two forms, written down where an author meets it
  (ADR-0045 decision 14). The count moved again first: `logcalls.handed` reports twelve brain log
  calls whose message is a bare name, all twelve bound at their module's own top level, and four are
  wrapped, `_UNREADABLE_CALL_LOG_MSG` at `brain_phase.py:170` joining `_NO_READING_LOG_MSG` at 226,
  `_CARD_TOO_SHORT` at `residency_moves.py:161` and `ABANDONED_MESSAGE` at `abandon.py:73`. None of
  the four is registered. Rendering both templates through the real registry machinery against the
  real files confirms both halves: the template naming the call is found zero times for each of the
  four and once for `_MESSAGE`, and `{name},` falls on the handing line in all five. So the failure
  message now names both, and its suite covers each on a wrapped fixture. The whitespace-folding
  registry form is not built and is not the close: it would overturn the rule in `searchtexts.py`
  that a search text is matched as written, which every other entry rests on, for one shape of one
  entry kind. What the shorter template gives up, that it locks the name rather than the call, is
  filed as [R-672](672-a-wrapped-calls-needle-holds-the-name-rather-than-the-call.md).
