# The unkept claim note follows replies that claim nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-10-29

`limit_notes` appends `UNKEPT_CLAIM_NOTE` ("Nothing in this message was kept in memory. Send
anything you want remembered again in a message of its own.") when `memory_withheld` holds and
`claims_kept` (`memory_claim.py`) finds a statement that something was noted or will be remembered.
Under the default `CORTEX_MEMORY_ON_TAINTED=skip`, `memory_withheld` holds on every turn that read
an MCP sidecar result, so the note follows any such reply whose sentence matches, whether or not the
person asked for anything to be remembered.

`claims_kept` returned `True` on 2026-10-29 for each of these sentences, none of which says that
anything was kept in memory:

| Sentence | Pattern |
| --- | --- |
| "As I noted above, the file has two lines." | `_NOTED` |
| "I will note that the page has no date." | `_NOTED` |
| "Noted: buy milk." (a line of a file read back) | `_PASSIVE` |
| "It has been noted by critics that the film is long." | `_PASSIVE` |
| "I have stored the result in memory.txt for you." | `_PUT`, since `\b` holds before `.txt` |

The K row of the change's draws ("What does notes.txt say?", five draws) passed, so no draw has
shown the note on such a reply yet
([readings](../../readings/remember-on-a-turn-not-kept.md#the-draws-of-the-change-2026-10-29)).

## What to do

1. Write rows first: file-reading and summarizing requests whose replies tend to use these forms,
   with a pass rule that counts a note on a reply that claims nothing as a failure.
2. Narrow the patterns to statements about the assistant's own memory (not a file named
   `memory.txt`, not "as I noted above"), and check that RC, R14 and T1 to T3 still pass.

## History

- 2026-10-29: filed from the closing audit of the unkept claim note.
