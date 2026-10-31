# A request to remember can call a file tool and store nothing

**Status:** done 2026-10-31
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

A file sidecar result is untrusted, so a turn that calls `list_allowed_directories` is tainted
and, unless `record_tainted_memory` is set, stores nothing. In the baseline of
[side-effect-tools-on-remember.md](../../readings/side-effect-tools-on-remember.md), "Please
remember this: my daughter is allergic to peanuts." called `set_volume` and then
`list_allowed_directories`, and the reply said "I've noted that your daughter is allergic to
peanuts." before the unkept note. The person asked for nothing but the fact, and the fact was
lost. [remember-on-a-turn-not-kept.md](../../readings/remember-on-a-turn-not-kept.md) found the
same call on 4 of 170 requests to remember a card number.

## What to do

1. Give `ToolSpec` a field saying a tool's results are untrusted, set by the tools registry on
   every MCP tool, and let `unasked_tools` (`unasked_tools.py`) read the turn's specs rather
   than core tool names, with an ADR first. It reads `set_volume` and `schedule_task` by the
   core's own name constants; the file sidecar's names belong to its MCP server, and nothing
   before a call says its result is untrusted (`ToolResult.trust` defaults to `UNTRUSTED`).
2. Write rows and a rule before a baseline. A withheld tool is refused by name, so the unasked
   call rate falls to zero by construction and needs no row; the rows decide what must not
   break: T01 of [reply-repeat-across-a-tool-call.md](../../readings/reply-repeat-across-a-tool-call.md),
   a request to remember that also asks which folders can be read, still calls its file tool,
   and R01 to R15 store their facts.

## History

- 2026-10-30: filed from the baseline of the side-effect tools check (R-901).
- 2026-10-30: corrected. Of the 242 draws of R01 to R15 run that night, 2 called a file tool,
  both `list_allowed_directories` on the peanuts row, too few for a baseline to show a drop.
  T01 called it in 20 of 20 draws, so a request to remember can ask for a file tool. No rule
  was written and nothing was built.
- 2026-10-31: done, with a different remedy. The separated pair of
  [R-952](952-withheld-unasked-tools-may-raise-forget-calls-on-a-remember-request.md) found that a
  shorter tool list raises forget calls, so leaving every MCP tool out was not built. The registry
  sets `ToolSpec.sidecar`, those tools stay listed, and a call to one on a request to remember that
  names no source is refused by name, which leaves the turn untainted. T01 and F01 to F05 called a
  file tool in 12 of 12 draws on both builds and R01 to R15 stored 15 of 15
  ([readings](../../readings/sidecar-tools-on-remember.md)). Filed
  [R-962](962-a-reply-after-a-refused-file-call-can-say-it-has-no-access.md) for the reply after a
  refusal.
