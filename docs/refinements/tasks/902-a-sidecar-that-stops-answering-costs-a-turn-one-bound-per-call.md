# A sidecar that stops answering costs a turn one bound per call

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`BoundedToolRegistry` ends one call that runs past `CORTEX_TOOLS_CALL_TIMEOUT_S` (60 s by default)
with `ToolError`, and nothing remembers it. When a sidecar stops answering but keeps its socket
open (a frozen process, a host under swap), the model calls another of the same sidecar's tools,
and each call waits the whole bound again. The turn ends at the round limit with no answer.

Reproduction ([readings](../../readings/overlay-tool-failure-flows.md#a-sidecar-that-stops-answering)):
on the brain directly, ask "Read club-notes.txt and tell me who collects the bulb order." and run
`docker pause` on the filesystem sidecar once the turn's first listing call is audited. The turn
made six more filesystem calls (`list_directory`, `search_files`, `list_directory`,
`read_text_file`, `search_files`, `list_allowed_directories`), each ending with "did not answer
within 60s", and ended after 386 s with the note "I stopped after 8 rounds of tool calls". The
overlay's chip read "waiting for a tool to finish" for those six minutes.

A stopped sidecar shows the same shape at a smaller price: with `read_text_file` confirmed, the
sidecar stopped while its card was open and the card approved, the call failed, the cortex asked
for the same read again behind a second card, then made three more calls that each failed in
about 2.5 s. The first failure's text, "stopped answering during this call", also misstates a
server that was down before the call began.

## What to do

1. Decide what the rest of the turn does after one call on a sidecar overruns the bound: fail
   that sidecar's later calls at once with a result text saying the server stopped answering, or
   withdraw its tools from the next round. Write the decision into ADR-0009.
2. Test over a fake sidecar that never answers that a second call costs no second bound, and
   repeat the reproduction to check the turn ends in about one bound with an answer.

## History

- 2026-10-26: filed from the tool failure flows on the `cortexn8` stack.
