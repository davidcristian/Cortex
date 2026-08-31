# The run an unfound needle quotes back is measured over a whole file, so it overstates itself

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** A reader acting on the quoted run and editing the wrong line, or a mention whose
template has to span more than one line, which would make a per line run the only kind there is.

Opened 2026-08-23 by the close of
[R-403](403-a-needles-literal-reddens-the-wrong-entry.md), which measured this while writing the
fault and chose to report the limitation rather than hide it.

`scripts/needles.py`'s `carried` returns the longest opening run of a rendered needle that the
file's text contains, and the fault quotes it back so a reader can see where the file stops
agreeing. A `Mention` names a file and not a line, so that run is taken over the whole text, and a
prefix satisfied on some **other** line makes it longer than the divergence in the line the reader
is actually looking at. Measured on the case the close was written for: with
`docker/docker-compose.yml`'s seam publish moved to `0.0.0.0`, the run over the needle
`"127.0.0.1:50051:50051"` still reaches `"127.0.0.1:`, carried by the redis publish forty lines
below, where the divergence in the intended line is at its second character.

**Why it was left.** The run is the weaker of the fault's two readings and it is worded to be true
of what was measured, "carrying no more of it than", so it misleads nobody who reads it literally.
The claim that carries the fault is whether the file still spells the constant's own value, which
is unaffected by this. Sharpening the run is a separate question about what a mention is scoped to,
and answering it inside a close about misattribution would have buried it.

**What would close it, and the reason it is not obvious.** The narrow fix is to take the run
per line and report the best one with the line number, which would have said `"1` and line 59 in
the case above. That is more useful and it is also a different claim, because the best line is
chosen by a heuristic (the longest run) rather than read off anything: a needle spanning two lines
has no best line at all, and this scan renders no multi-line template today and is not
built to reject one either. So the change needs a decision about whether a mention is a claim about a
file or about a line, and that decision reaches `Mention.occurrences`, which counts over a file
today. Re-derive before starting: this description is a reading of `scripts/needles.py` and
`scripts/crosscheck.py` as they stood the day it was written.
