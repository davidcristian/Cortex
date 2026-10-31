# A file question answered without a call shows invented folders with no note

**Status:** done 2026-10-31
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

A message that asks which folders the cortex can read is often answered with no file tool call,
and the reply then lists folders that do not exist, such as `/home/user/Documents`, while the
file sidecar's one folder is `/projects`
([file-request-without-a-call.md](../../readings/file-request-without-a-call.md)). Memory
stores no such turn (`asks_files` in `memory_withheld`), so a later chat does not repeat the
list, but the reply itself is shown and saved in the chat with nothing telling the person it was
not read from their files. Two of the 20 candidate draws listed invented folders until the
reply's token limit ended them.

A note the brain appends after a typed check of the reply is the form that stopped other false
claims (`schedule_claim.py`, `memory_claim.py`). The check here reads the reply for a path or a
listed folder on a turn whose message `asks_files` and that ran no file tool. The core does not
know which advertised tools are file tools, since MCP names come from the server, so the
condition is an untainted turn, as for the memory check.

## What to do

1. Write rows and a pass rule into the readings before drawing: F01 to F03 of the record above,
   five draws each, counting draws with no call whose reply names an invented folder and shows
   no note; plus draws that call the tool, which must show no note.
2. Build the note and its typed check, and draw the candidate on the same rows.

## History

- 2026-10-30: filed when a file question that read no tool output stopped being stored, leaving
  the shown reply without a note.
- 2026-10-31: done. `claims_folders` and `UNREAD_FOLDERS_NOTE` (`file_claim.py`) close such a reply: on
  [the rows](../../readings/file-request-without-a-call.md#the-note-on-the-shown-reply-the-replay-and-the-draws-2026-10-31)
  all 9 draws with no call that named invented folders ended with the note, and no draw that called a
  file tool did. The check reads an untainted turn, so it runs with memory on or off.
