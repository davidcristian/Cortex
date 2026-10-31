# A reply after a refused file call can say it has no access

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-10-31

On a request to remember that names a source `unasked_sidecar_tools` (`unasked_tools.py`) does not
read, such as "Remember the address on my lease.", a call to a file tool is refused by name. Each
of the 4 such draws in
[sidecar-tools-on-remember.md](../../readings/sidecar-tools-on-remember.md#the-draws-2026-10-31)
then asked the person for the file or the value, and two said "I don't have access". The sidecar
is reachable, so that is not exact, and the person's next message reaches the tool one message
later.

## What to do

1. Write rows and a rule before a baseline, with M01 and M02 of that record among the rows.
2. Check whether reading "from my" and "on my" as a source settles it. Near-miss tests come first,
   and every recorded draw message is replayed through the old and new reader. A word read wrongly
   only allows the tool, which is the shipped behaviour of a message that names a source.
3. Prefer that over a new wording of `UNASKED_MSG`, which every refusal of `set_volume` and
   `schedule_task` shares.

## History

- 2026-10-31: filed from the rows of
  [R-950](950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md).
