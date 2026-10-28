# An answer from cut results does not say they were cut

**Status:** done 2026-10-28
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

When the results of one loop share `RESULT_ROOM_CHARS` (`tool_cut.py`), each of several reads in a
round keeps only a part, and the note after it says so. The cortex then answers as though it had
read every file whole. The model is told the result was cut; the person is not.

Reproduction (2026-10-26, the `cortexn8` stack, the cortex at context 16,384): four logs of 300
lines each in the file sidecar's root, then over `Converse` "Call read_text_file four times in one
step, once each for /projects/alpha.log, /projects/bravo.log, /projects/charlie.log and
/projects/delta.log (not read_multiple_files), then tell me which worker appears most often across
them." Each result kept about 1,500 characters, about 20 lines. The reply listed a count for each
worker, about 20 lines a file in all, opened "Based on the logs from the four files" and named
worker-9, with no word that only the first part of each file was read
([readings](../../readings/overlay-tool-failure-flows.md#a-file-far-past-the-context)).

## What to do

1. Write the rows and the pass rule into the readings before any change: the question above and
   two more that read several files at once, five sampled runs each on the current build. A run
   passes when its reply says the counts or the summary cover only part of the files. Baseline
   first.
2. The likely change is in the result text, not the prompt: `ROOM_SHARED` and `RESULT_CUT_NOTE`
   ask the model to tell the person which part it read when it answers from a cut result. It ships
   only if the same rows pass at least four runs in five where the baseline did not.

## History

- 2026-10-26: filed from the repeat of the several-reads reproduction on the `cortexn8` stack.
- 2026-10-28: rows and pass rule written into
  [tool-result-room.md](../../readings/tool-result-room.md#an-answer-from-cut-results) before the
  baseline, on the `cortexn9` stack without delegation. `RESULT_CUT_NOTE` and `ROOM_SHARED` now
  ask the model to tell the person its answer covers only the part it read: the four-reads row
  went from 1 of 5 to 5 of 5, and the other two rows stayed at or rose to 5 of 5.
