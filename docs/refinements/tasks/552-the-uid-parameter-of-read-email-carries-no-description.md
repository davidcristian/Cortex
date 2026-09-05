# The uid parameter of read_email carries no description

**Status:** landed 2026-09-05
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-09-05 by the close of
[548](548-an-empty-folder-read-raises-instead-of-answering-not-found.md), which settled what a
uid is on the port's side and told the model nothing.

`read_email(folder, uid)` in `brain/packages/email/src/cortex_email/server.py` describes
`folder` from `FOLDER_HELP` and leaves `uid: str` bare, so the schema a model reads says nothing
about where a uid comes from or what the not-found answer means. Since the close, a string that
is not a uid (`abc`, `01`, `2,1`, `1:*`) is answered `message <uid> not found in <folder>` with
no command sent, which is true and is the trusted own text, and a model reading it has no
sentence telling it that a uid is the number inside the brackets of a `search_emails` line,
spelled exactly as that line spells it, or that a not-found answer is final for that folder
rather than something to retry with a likelier number.

**What would close it.** A `UID_HELP` in `values.py` beside `FOLDER_HELP`, spent by the tool
signature the way `FOLDER_HELP` is, saying those two things in the instructing register the
other descriptions use, and a server test asserting the generated schema carries it, the shape
the attachment descriptions have.

**Why it was left.** The description is prompt-facing prose, which the search-dialect addendum
wrote from a live pass rather than from the standard, and no live pass has shown the cortex
misspelling a uid yet; the close it would ride on is a change to the adapter, and the two should
not share a commit.

## Trail

- 2026-09-05: opened by the close of
  [548](548-an-empty-folder-read-raises-instead-of-answering-not-found.md), which made a string
  that is not a uid a not-found answer and left the parameter undescribed.
- 2026-09-05: landed. The claim held as written, and one fact the entry did not name went in
  beside its two: a uid names a message only within the folder it was listed in. `UID_HELP` in
  `brain/packages/email/src/cortex_email/values.py` says where the number comes from, that it
  is per folder, and that a not-found answer is final; `read_email` spends it as it spends
  `FOLDER_HELP`, and a server test reads the three facts off the generated schema. Measured
  through `build_tool_registry` against the shipped sidecar on a live Bridge, `describe_tools()`
  hands the cortex the description byte for byte. Written up in the
  [ADR-0022 addendum on what a uid is](../../adr/ADR-0022-email-write-confirmer.md#addendum-2026-09-05-read_email-says-what-a-uid-is),
  with the mutation table. Opens
  [571](571-the-cortexs-reading-of-the-uid-description-is-unmeasured.md) and
  [572](572-the-not-found-answer-states-no-correction-where-the-folders-does.md).
