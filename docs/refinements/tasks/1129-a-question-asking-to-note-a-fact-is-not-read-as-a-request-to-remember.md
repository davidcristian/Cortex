# A question asking to note a fact is not read as a request to remember

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-11-10

On 2026-11-10 at 06:32 local, chat `s17-m5` on the shared stack sent `Anna said: "remind me every
day at 8 to water the plants". Can you note that she likes plants?`. The cortex called
`list_allowed_directories` first, which taints the turn, so nothing was kept, and the reply said
`I've noted that you like plants` before the unkept note
([readings](../../readings/overlay-mentioned-words-flows.md)). The fact was lost and the reply
named the wrong person. The two later draws called no file tool and kept the exchange. At 06:50
the same message (chat `s18-m5-3`) called `list_allowed_directories`, `list_directory` and
`read_text_file` twice beside `schedule_task` and stopped at the round cap with no answer.

`asks_kept` (`memory_request.py`) reads `Please note that Anna likes plants.` as a request to
remember but not `Can you note that Anna likes plants?`, so `unasked_sidecar_tools` refuses no
file tool on the question form, while the statement form has the refusal
[R-950](950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md) built.

## What to do

1. Write near misses as tests first: `Can you note the time?` (a question about the clock),
   `Can you note down the steps for me?` in a file request, `Did you note that?`, a negation.
   Replay every readings string through the old and new `asks_kept`.
2. Read `can you`, `could you` or `would you` before `note`, `remember` or `keep in mind` with an
   object clause as a request to remember. Its safe direction depends on the reader that uses
   it: the sidecar refusal keeps the tool when unsure, so a missed form costs a lost fact, not a
   refused call.
3. Draw the question form at least eight times on both builds and count the file calls.

## History

- 2026-11-10: filed from the mentioned-words flows.
