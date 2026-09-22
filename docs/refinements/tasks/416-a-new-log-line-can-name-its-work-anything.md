# A new log line can name its work anything, the registry covering only the modules it lists

**Status:** declined 2026-09-12
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`scripts/logcouplings.py` ties five declarations to the modules that write them and the runbooks
that quote them, so a rename that moves one place and not the others makes the check fail. What it
does not cover is a place nobody registered. A module added tomorrow that writes
`extra={"chat_id": ...}` appears in no match, so every match still resolves, the check still
passes, and the split those closed entries were about is back under a new name. That is the
presence test working as designed, the same limit every part of that registry has.

The two ways out differ in kind. The cheap one is a rule nobody enforces, a sentence in
`log_fields.py` and in the module contracts saying that a line naming work takes one of the five
names and that adding a module means adding a match. The real one is a scan that reads every
`extra=` in the brain and compares each key that looks like an identity with the vocabulary, which
is a twelfth cross-tree check with an ADR of its own, and which has to solve the indirection three
sinks already use: `converse_stream.py`, `cortex_memory/audit.py` and `cortex_tools/audit.py` all
build a `fields` dict and pass it by name, so a scan that reads only `extra={...}` literals would
miss exactly the lines with the most identities on them. It also needs an answer for what "looks
like an identity" means, since the Redis codecs write four of the five as hash keys of their own
and must not be compared with the log vocabulary at all.

## History

- 2026-08-24: opened by the close of
  [R-339](339-two-names-for-one-conversation-across-the-brains-log-fields.md) and
  [R-394](394-the-fired-schedule-item-has-two-field-names-across-the-brains.md), whose registry part covers every
  place that writes the vocabulary today and no place written later. Recorded in ADR-0042.
- 2026-08-25: the arithmetic moved and the argument did not. Two scans were added together, one
  comparing every volume an image declares with a mount some compose service makes and one
  comparing the committed Rust stub with the comments the proto has, so AGENTS.md then named eight
  scans and the one this entry weighs would be the ninth. Adding a scan is still a change to the
  contract rather than to a data file.
- 2026-09-09: trigger checked and not fired, read off every `extra=` dict literal in
  `brain/packages/*/src`. Thirteen modules attach one of the five names that way and the registry
  lists all thirteen, `cortex_memory/audit.py` reaching them through its `fields` dict instead.
- 2026-09-09: the nearest thing to a firing, recorded so the next reader does not work it out
  again. Four `extra=` keys outside the vocabulary end in `id`: `pid` in the model host's
  supervisor and its children, `boot_id` in `residency_watch.py` and the model-host adapter, and
  `extra={"id": confirm_id}` in `cortex_orchestrator/confirm.py`. None is a work identity under the
  dispatch stamp's reading, and the confirm line has been there since 2026-07-08, so it is not an
  arrival either. The trigger now says that in as many words.
- 2026-09-09: the arithmetic moved again and the argument still has not. AGENTS.md names eleven
  cross-tree scans, so the check this entry weighs would be the twelfth.
- 2026-09-12: declined, on the count this entry asked for. Every reading above still holds: the
  same thirteen modules attach one of the five in an `extra=` dict literal, the registry lists all
  thirteen plus `cortex_memory/audit.py`, and the keys outside the vocabulary that end in `id` are
  three names over five places rather than four keys as the line above says. The new reading is the
  rate. Sixteen identity-naming lines have been written since the vocabulary was settled, in
  `brain_phase.py`, `runner.py`, `swap_conductor.py`, `swap_recovery.py` and `swap_settle.py`, and
  every one of the five modules gained its registry rows in the commit that wrote its lines. In the
  eighteen days since that work finished, one identity-naming line was added, beside ten log calls
  of other kinds. So the scan does not justify its ADR, and what was written instead is the
  sentence: `log_fields.py` and [modules/brain-core.md](../../modules/brain-core.md) now say that
  the registry covers the modules it lists, that a module which starts using one of the five is
  registered in the same change, and that one nobody registered can name an identity however it
  likes with every check passing. Recorded in ADR-0042.
