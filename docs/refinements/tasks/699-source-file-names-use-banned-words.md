# Source file names use words the prose table bans

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-19

The prose rules reach documents, comments and docstrings, and stop at identifiers. Twelve source
files are named after a word the table in AGENTS.md bans, so a reader who learns the vocabulary
from the rules meets it again in the file list.

In the brain and the body: `brain/packages/inference/src/cortex_inference/lever.py`,
`brain/packages/inference/tests/test_lever.py`, `brain/packages/inference/tests/test_image_arm.py`,
`brain/packages/core/src/cortex_core/health_gate.py`,
`brain/packages/core/src/cortex_core/residency_sweep.py`,
`brain/packages/core/src/cortex_core/url_spellings.py`,
`brain/packages/orchestrator/tests/recall_trail_probe.py`,
`brain/packages/orchestrator/tests/test_schedule_live_seam.py`,
`brain/packages/model_manager/tests/test_seams.py` and `body/app/src-tauri/src/seam.rs`. In the
checks: `scripts/coverage_gate.py` and `scripts/needles.py`. Five more names in `scripts/` join one
of those words to another word, which is why the check reads them as ordinary names:
`gatecalls.py`, `levercouplings.py`, `seamcouplings.py`, `trailcouplings.py` and `trailwidth.py`.

Two names are larger than a file. The brain package `cortex_seam` is what every other brain package
imports the wire code through, and `CORTEX_SEAM_TOKEN` is the environment variable the body and the
brain both read; it is set in the justfile, in the compose stack and in the live Rust suite, and it
is named in four runbooks, two module contracts, a decision record, a readings record and the host
backlog.

**What would close it.** Either a rename, each file with its imports, its documents and any list
naming it, and `CORTEX_SEAM_TOKEN` with every place that sets or reads it; or a decision written
down that the names stay, with the reason. Nobody has weighed the rename against the cost of
touching working code for a name, and until somebody does this is a question rather than a job.

## History

- 2026-09-19: opened after a reading of the file list against the table.
