# A new log line can name its work anything, the registry holding only the modules it lists

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a module the log-vocabulary registry does not list attaching a work identity under a
name of its own, or a sixth identity arriving with nowhere to be registered
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
same limit every part of that registry has, but it bites harder here: a log line is a thing this
repo adds weekly, where a compose default or a stylesheet property is added once a quarter.

The two ways out are different in kind. The cheap one is a rule with nobody enforcing it, a
sentence in `log_fields.py` and in the module contracts saying that a line naming work takes one of
the five names and that adding a module means adding a mention. The real one is a scan that reads
every `extra=` in the brain and holds each key that looks like an identity to the vocabulary, which
is a seventh cross-tree gate with an ADR of its own, and which has to solve the indirection three
sinks already use: `converse_stream.py`, `cortex_memory/audit.py` and `cortex_tools/audit.py` all
build a `fields` dict and pass it by name, so a scan that reads only `extra={...}` literals would
miss exactly the lines with the most identities on them.

**Why it was left.** The close it came out of was a rename plus the registry rows that hold it, and
the rows are proved able to fail twelve ways. A seventh gate is a bigger decision than the defect
that prompted it: AGENTS.md names six cross-tree scans and says all six run unconditionally, so
adding one is a change to the contract and not to a data file. It also needs a real answer to what
"looks like an identity" means, since the Redis codecs spell four of the five as hash keys of their
own and must not be held to the log vocabulary at all.

**What would close it.** Decide between the rule and the scan, on evidence rather than taste: count
how many log lines naming a work identity have been added since the vocabulary was written down,
and how many of them were added in a module the registry already lists. If most new lines land in
listed modules, the presence check plus a sentence is enough and the scan is not worth its ADR. If
they land in new modules, build the scan, and build it on `ast` rather than on text, resolving a
`fields` name to the dict literal assigned to it in the same function so the three sinks are not
its blind spot.

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
