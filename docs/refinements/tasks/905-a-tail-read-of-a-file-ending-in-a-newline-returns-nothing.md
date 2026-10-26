# A tail read of a file ending in a newline returns nothing

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The filesystem sidecar's `read_text_file` with `tail` 1 returns an empty result for a file that
ends in a newline, as nearly every text file does: it counts the empty string after the last
newline as the last line. The cortex reads that as the file's last line and tells the person it
is empty.

Reproduction ([readings](../../readings/overlay-tool-failure-flows.md#a-file-far-past-the-context)):
put a log whose last line is an `ERROR` line, ending in a newline, in the sidecar's root and ask
"Read server-log.txt and tell me what the last line says." on the brain directly. The cortex
called `read_text_file` with `tail` 1, the audit line has `result_chars=0`, and the reply was
"The last line of `server-log.txt` is empty."

## What to do

1. Check whether the image the sidecar runs (`docker/docker-compose.tools.yml`) has a newer
   release that drops a trailing empty line from `tail` and `head`, and move to it if so.
2. Otherwise decide between a note in the tool's description the cortex is offered and a fix in
   the image, write it into the tools runbook, and repeat the reproduction.

## History

- 2026-10-26: filed from the tool failure flows on the `cortexn8` stack.
