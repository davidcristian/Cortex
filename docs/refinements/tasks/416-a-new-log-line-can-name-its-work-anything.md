# A new log line can name its work anything, the registry holding only the modules it lists

**Status:** declined 2026-09-12
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-24 by the close of
[R-339](339-two-spellings-of-one-conversation.md) and
[R-394](394-the-fired-item-has-two-spellings-in-the-logs.md), which put the brain's log vocabulary
behind `scripts/logcouplings.py` and can hold only what that file lists.

The new part ties five declarations to the modules that spell them and the runbooks that quote
them, so a rename that moves one place and not the others makes the gate fail. What it does not cover
is a place nobody registered. A module added tomorrow that writes `extra={"chat_id": ...}` is spelled in
no mention, so every mention still resolves, the gate stays green, and the split the two closed
entries were about is back with a new spelling. That is the presence check working as designed, the
same limit every part of that registry has.

The two ways out are different in kind. The cheap one is a rule with nobody enforcing it, a
sentence in `log_fields.py` and in the module contracts saying that a line naming work takes one of
the five names and that adding a module means adding a mention. The real one is a scan that reads
every `extra=` in the brain and holds each key that looks like an identity to the vocabulary, which
is a twelfth cross-tree gate with an ADR of its own, and which has to solve the indirection three
sinks already use: `converse_stream.py`, `cortex_memory/audit.py` and `cortex_tools/audit.py` all
build a `fields` dict and pass it by name, so a scan that reads only `extra={...}` literals would
miss exactly the lines with the most identities on them.

**Why it was left.** The close it came out of was a rename plus the registry rows that hold it, and
the rows are proved able to fail twelve ways. Another gate is a bigger decision than the defect
that prompted it: AGENTS.md names eleven cross-tree scans and says all eleven run
unconditionally, so adding one is a change to the contract and not to a data file. It also needs a real answer to what
"looks like an identity" means, since the Redis codecs spell four of the five as hash keys of their
own and must not be held to the log vocabulary at all.

**Why it is declined.** The entry asked for the count that would pick between the two ways out, and
the count says the cheap one. Every identity-naming line written since the vocabulary landed was
registered in the commit that wrote it, sixteen lines over five modules, no exceptions; and once
that work finished on 2026-08-25, eighteen days produced one such line, in `runner.py`, which the
registry already listed. Ten log calls of any kind were added in the same eighteen days, so it is
the identity-naming line that is rare rather than the log line, and the premise that this hole
bites weekly is wrong by an order of magnitude. So the scan does not earn its ADR, and what landed
is the sentence: `log_fields.py` and
[modules/brain-core.md](../../modules/brain-core.md) now say that the registry holds the modules it
lists, that a module which starts naming one of the five is registered in the same change, and that
one nobody registered can spell an identity however it likes with every gate green.

## Trail

- 2026-08-24: opened by the close of
  [R-339](339-two-spellings-of-one-conversation.md) and
  [R-394](394-the-fired-item-has-two-spellings-in-the-logs.md), whose registry part holds every
  place that spells the vocabulary today and no place that has not been written down yet. Recorded
  in the ADR-0029 addendum that added the part.
- 2026-08-25: the arithmetic above has moved and the argument has not. Two scans landed together,
  one holding every volume an image declares to a mount some compose service makes and one
  holding the committed Rust seam stub to the comments the proto carries, so AGENTS.md now names
  eight and the gate this entry weighs would be the ninth. What that changes is only the number:
  adding a scan is still a change to the contract rather than to a data file, and the harder half
  of this entry, what "looks like an identity" means when the Redis codecs spell four of the five
  as hash keys of their own, is untouched by either.
- 2026-09-09: trigger checked and not fired, read off every `extra=` dict literal in
  `brain/packages/*/src`. Thirteen modules attach one of the five names that way and the registry
  lists all thirteen, `cortex_memory/audit.py` reaching them through its `fields` dict instead.
  The five declarations, the runbook far sides and the three indirect sinks are all as this entry
  describes them.
- 2026-09-09: the nearest thing to a firing, recorded so the next reader does not re-derive it.
  Four `extra=` keys outside the vocabulary end in `id`: `pid` in the model host's supervisor and
  its children, `boot_id` in `residency_watch.py` and the model-host adapter, and
  `extra={"id": confirm_id}` in `cortex_orchestrator/confirm.py`. None is a work identity under
  the dispatch stamp's reading, and the confirm line has been there since 2026-07-08, so it is
  not an arrival either. The trigger now says that in as many words, because "a work identity"
  was decidable only by argument.
- 2026-09-09: the arithmetic has moved again and the argument still has not. AGENTS.md names
  eleven cross-tree scans, so the gate this entry weighs would be the twelfth, and the body says
  eleven rather than the six it was written against.
- 2026-09-12: declined, on the count the entry itself asked for. Re-derived first and every
  reading above holds: the same thirteen modules attach one of the five in an `extra=` dict
  literal, the registry lists all thirteen plus `cortex_memory/audit.py`, and the four keys
  outside the vocabulary that end in `id` are still those four, which is three names over five
  places rather than four keys as that line says. The new readings are the rate. Sixteen
  identity-naming lines have been written since the vocabulary landed, in `brain_phase.py`,
  `runner.py`, `swap_conductor.py`, `swap_recovery.py` and `swap_settle.py`, and every one of the
  five modules gained its registry rows in the commit that wrote its lines, the swap path's four
  in the same hour as the vocabulary itself. In the eighteen days since that work finished, one
  identity-naming line was added, beside ten log calls of other kinds. Recorded in the ADR-0029
  unregistered-line addendum, which carries the derivation.
