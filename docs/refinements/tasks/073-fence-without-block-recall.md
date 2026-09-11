# Fence-without-block recall mode

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Trigger:** taint-spread on tangential recall proving too blunt.
**Verified:** 2026-09-11

It was recorded inside the context-preserving tainted-memory recording entry
([R-072](072-tainted-memory-recording.md)), in its list of what remains behind the same seams
(ADR-0019 deferred). The fragment, verbatim: a
**fence-without-block** recall mode if taint-spread on tangential recall is too blunt.

## Trail
- 2026-09-11: **Not fired.** The mechanism is unchanged: `_recalled_context` in `turn_context.py`
  fences a recalled tainted memory and taints `context.taint`, so a tangential tainted hit still
  closes the turn's gated tools. Whether that has bitten was read from the store rather than
  reasoned about: the stack was down, so postgres was started alone from its persisted volume, and
  `memories` holds 2 rows, both with `tainted = false`, so no tainted memory has ever been recalled
  on this deployment, tangentially or otherwise, and the bluntness the trigger names has had
  nothing to show itself on. Postgres was stopped again afterwards. One design since has chosen the
  mode this entry defers, for a different message: the summarizing window's recap is fenced at
  both ends without spreading taint (ADR-0038 untrusted-recap addendum), because the plain history
  window already hands the model the same text unfenced. That argument does not carry to recall,
  whose fenced text is nowhere else in the window. A precise fence over recall would need the
  persisted per-turn marker [R-082](082-replayed-quoted-injection.md) waits on, so the two entries
  meet at one design.
