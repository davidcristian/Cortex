# The swap path names its work with bare nouns while the rest of the brain suffixes them

**Status:** done 2026-08-24
**Area:** cross-cutting
**Origin:** [ADR-0046](../../adr/ADR-0046-work-identities-on-log-lines.md)

Eleven log records on the swap path name their work with a bare noun. `swap_conductor.py` writes
`extra={"turn": turn_id}` on four of them, which is the same identity `engine.py`,
`turn_context.py` and `converse_stream.py` write as `turn_id` and the tool audit prints under that
name, so `grep turn_id=t-9` gathers a turn's failures and its tool calls and misses every refusal
of a handoff that turn asked for. One of those four also has `active_handoff`, the id of the
handoff already holding the swap. The other seven records name a handoff `handoff`: three in
`swap_settle.py`, one in `swap_recovery.py`, and three in `brain_phase.py`.

The turn half is a second name for something the brain has settled, and nothing checks it:
`scripts/logcouplings.py` ties every place that writes `turn_id` to one declaration, and a bare
`turn` is not that string. The handoff half is a different question, because a handoff is a sixth
identity the dispatch stamp does not have, so it has no settled name to be wrong against; the
answer for the turn decides the shape of the answer for the handoff.

The remedy is to rename the conductor's four `turn` fields to `turn_id` and register that module
with the turn entry in `scripts/logcouplings.py`. Then decide whether a handoff joins the
vocabulary as `handoff_id`, which would make `log_fields.py` have six names and needs the swap
runbook's pasted line updated with it, or whether the swap path's nouns are deliberately its own.
The pasted line shows the problem either way: it renders the field as `handoff=<turn id>`, so a
reader is already being told that this id and a turn id are the same number under two names.

## History

- 2026-08-24: opened by the close of
  [R-339](339-two-names-for-one-conversation-across-the-brains-log-fields.md) and
  [R-394](394-the-fired-schedule-item-has-two-field-names-across-the-brains.md), which settled one name per work
  identity for the five the dispatch stamp has, and found this third instance of the same problem
  already in the tree and older than either entry. Recorded in ADR-0046 decision 1.
- 2026-08-24: closed. The counts held: four `turn` records in the conductor, seven `handoff` ones
  across the settler, boot recovery and the deep phase. The open question was answered where the id
  is created rather than at any place that logs one: `EscalationSlot.snapshot` writes
  `handoff_id=turn_id` and is the only production construction of a record, so a handoff id is the
  escalating turn's id and there is no sixth identity. All eleven now name the work `turn_id`, the
  one line that names two turns writes the second `active_turn_id` with the qualifier in front so a
  grep for `turn_id` still reaches it, and the swap runbook's pasted line follows with a sentence
  saying why the two words are one number. The registry's turn entry grew from four matches to
  eleven, two of them with a count, and it covers the qualified name through a template rendering
  the same declared value. Proved able to fail seven ways over the brain suite and ten over the
  crosscheck registry. Six of the eleven records are checked by a test and five by the registry
  alone. Argued in ADR-0046 decision 4, with the affected surface recorded at ADR-0030 and the
  registry part at ADR-0029. Opened
  [R-417](417-the-swap-path-never-names-the-conversation.md), which is the same reading one
  identity over.
