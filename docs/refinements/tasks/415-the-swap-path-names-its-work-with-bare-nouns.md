# The swap path names its work with bare nouns while the rest of the brain suffixes them

**Status:** landed 2026-08-24
**Area:** cross-cutting
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-24 by the close of
[R-339](339-two-spellings-of-one-conversation.md) and
[R-394](394-the-fired-item-has-two-spellings-in-the-logs.md), which settled one name per work
identity for the five the dispatch stamp carries and left this third instance of the same shape
outside the vocabulary they settled.

Eleven log records on the swap path name their work with a bare noun. `swap_conductor.py` writes
`extra={"turn": turn_id}` on four of them, which is the same identity `engine.py`, `turn_context.py`
and `converse_stream.py` spell `turn_id` and the tool audit prints under that name, so `grep
turn_id=t-9` gathers a turn's failures and its tool calls and misses every refusal of a handoff
that turn asked for. One of those four also carries `active_handoff`, the id of the handoff already
holding the swap. The other seven records name a handoff `handoff`: three in `swap_settle.py`, one
in `swap_recovery.py`, and three in `brain_phase.py`, which spells the name at two places and logs
it on three lines.

The turn half is a plain second spelling of a name the brain has now settled, and it is held by
nothing: `scripts/logcouplings.py` ties every place that spells `turn_id` to one declaration, and a
bare `turn` is not that string, so the registry does not reach it. The handoff half is a different
question, because a handoff is a **sixth** identity that the dispatch stamp does not carry, so it
has no settled name to be wrong against yet; what makes it worth deciding together is that the
answer for the turn decides the shape of the answer for the handoff.

**Why it was left.** The two entries that closed were about the conversation and the fired item,
and their surfaces are the recall trail, the rank, the ticker and two runbooks. The swap path has
its own documented lines, including a pasted `handoff=<turn id>` in
[model-swap.md](../../runbooks/model-swap.md), and renaming a field a runbook prints verbatim is
the same slice again on a different ADR's surface. Doing it inside a close about two other
identities would have buried it.

**What would close it.** Rename the conductor's four `turn` fields to `turn_id` and register that
module with the turn entry in `scripts/logcouplings.py`, which is a mechanical change the existing
gate then holds. Then decide whether a handoff joins the vocabulary as `handoff_id`, which would
make `log_fields.py` carry six names and needs the swap runbook's pasted line updated with it, or
whether the swap path's nouns are deliberately its own and that is written down where a reader of
those lines will find it. The pasted line shows the problem either way: it renders the field as
`handoff=<turn id>`, so a reader is already being told that this id and a turn id are the same
number under two names, which is the question the rename would answer or retire.

## Trail

- 2026-08-24: opened by the close of
  [R-339](339-two-spellings-of-one-conversation.md) and
  [R-394](394-the-fired-item-has-two-spellings-in-the-logs.md), whose re-derivation found the
  third surface the second of them was explicitly waiting for, already in the tree and older than
  either entry. Recorded in the ADR-0009 one-vocabulary addendum.
- 2026-08-24: landed. Re-derived first, and the counts held: four `turn` records in the
  conductor, seven `handoff` ones across the settler, boot recovery and the deep phase. The
  question this entry left open was answered at the mint rather than at any site that logs one:
  `EscalationSlot.snapshot` writes `handoff_id=turn_id` and is the only production construction of
  a record, so a handoff id **is** the escalating turn's id and there is no sixth identity. All
  eleven now name the work `turn_id`, the one line that names two turns spells the second
  `active_turn_id` with the qualifier in front so a grep for `turn_id` still reaches it, and the swap
  runbook's pasted line follows with a sentence saying why the two words are one number. The
  registry's turn entry grew from four mentions to eleven, two of them pinned to a count, and it
  holds the qualified spelling through a template rendering the same declared value. Proved able to
  fail seven ways over the brain suite and ten over the crosscheck registry, both tabled. Six of
  the eleven records are pinned by a test and five are held by the registry alone. Argued in the
  ADR-0009 sixth-name addendum, with the surface recorded at ADR-0030 and the registry part at
  ADR-0029. Opened
  [R-417](417-the-swap-path-never-names-the-conversation.md), which is the same reading one
  identity over.
