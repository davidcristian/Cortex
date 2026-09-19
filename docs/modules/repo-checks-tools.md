# The other command-line modules

The thirteen cross-tree scans are in [repo-checks-scans.md](repo-checks-scans.md) and the full
module list is in [repo-checks.md](repo-checks.md). This document covers the rest: three modules
that check one thing each, and five that report a measurement and decide nothing.

## `coverage_gate.py PATH --rustc TEXT --llvm-cov TEXT`

Reads a `cargo llvm-cov --json --summary-only` export, requires exactly one `data[]` entry, and
requires `covered == count` for each of `data[0].totals.{lines,regions,branches}`. The producer's
own `percent` is never trusted and displayed percentages are recomputed. A metric with `count == 0`
passes with a printed note. Malformed, missing or non-UTF-8 input gives a typed error on stderr and
exit 1 with no result printed. Exit 0 only when every check passes.

**This is the whole Rust coverage result, not the branch half of it** (ADR-0002 decision 12).
cargo-llvm-cov's own `--fail-under-lines` and `--fail-under-regions` were removed from the
measurement: with the report diverted by `--json --output-path` they exit 1 printing nothing at
all, which pre-empted this check with a silent failure while restating a threshold it already
enforced.

It also attributes the numbers it judges. The export records its own writer in
`cargo_llvm_cov.version` beside the llvm export format's `version`, and both are required.
`check-body` passes what it probed: `--rustc` is relayed into the result because the compiler is
absent from the export, and `--llvm-cov` must appear in the export's own record, so an export the
running tool did not write fails however good its numbers are. Neither version is fixed on either
side (ADR-0002 decision 11), which is why a result has to state them. Both relays are required
arguments (ADR-0002 decision 13): a run missing either exits 2 on argparse's usage error, having
printed nothing. Results print in order, the attribution lines first, then one `PASS` or `FAIL`
line per metric.

## `ci_paths.py`

Decides which toolchain CI jobs must run for a set of changed files (ADR-0006). It reads
newline-separated repo-relative paths, the output of `git diff --name-only`, on stdin, ignoring
blank lines. Each path is classified by ordered rules, first match wins, and the result is the
union over all paths; the normative rule list lives in ADR-0006 and in the module's own `RULES`
table, which change together.

It writes exactly four `GITHUB_OUTPUT`-format lines to stdout, in order: `python=true|false`,
`rust=true|false`, `overlay=true|false` and `shell=true|false`, and nothing else. The overlay is
the `body/app/` React tree, checked by `check-overlay`; its Tauri subtree `body/app/src-tauri/` is
Rust and is split off the overlay to a `rust+shell` result, which sets `rust` for that subtree's
format check inside `check-body` and `shell` for the separate job that runs `check-shell`. One
`ci-paths: PATH -> RESULT` line per path goes to stderr so CI logs show why a job ran. Empty input
gives four falses. An unmatched path sets all four, because unknown means over-testing rather than
under-testing. It always exits 0, classification having no failure mode. `shell` is the one output
no other job reads, so two tests check that routing from both sides.

## `commitlint.py MESSAGE_FILE [--repo DIR] [--rules FILE]`

The machine-checkable half of the AGENTS.md commit rules, run at the `commit-msg` stage next to
conventional-pre-commit. The header, meaning the first non-comment line, must be at most 72
characters, lowercase, and without a trailing period. A header that is not shaped like a
Conventional Commit passes silently, structure being the other hook's subject, and `Merge `,
`fixup! `, `squash! ` and `amend! ` headers are exempt including their bodies, because that wording
is git's and not the author's.

The body is at most 50 words (`MAX_BODY_WORDS`), counted by `length_problems` over the lines the
paste walk left as prose, so a fenced mutation table and a pasted command cost nothing. The count
is reported once, with its number.

Every line below the header must wrap at 72 (`MAX_BODY_WIDTH`), checked separately so one long
subject is one complaint. A line past it that could have been wrapped fails; `too_wide` exempts one
whose longest word alone is over the wrap, since a URL, a path or a long identifier has nowhere to
break. `classify_lines` is the single walk that decides each line's kind and reports any fence left
open (ADR-0026 decisions 10 and 11). A line inside a fenced block and a line whose first token is a
bare `$` are pastes; moving a newline inside one would change what it says. Line 1 is the header
and is prose by construction, so no message exempts its own subject. A fence left open at the end
of the walk is reported, since otherwise one stray fence would exempt every line after it. A
leading indent is deliberately not a signal, and a `BREAKING CHANGE:` footer is prose.

**A paste is exempt from the wrap rule, the word count and the dash ban, and from nothing else.**
All three are about the text as typed and have no remedy inside a paste. The ban on volatile
references and the commit-hash check are about the message still reading correctly after what it
points at moves, which does not depend on who typed the pointer. Across the whole message it also
reports a dash used as punctuation (em dash, en dash, spaced ASCII `--`) and volatile references:
a slice number, a decision-record number, the roadmap, or a numbered assumption, increment or
decision. Hex tokens
are resolved against `--repo` (default `.`) with `git cat-file`, so only a token that really is a
commit in this repository is reported; action SHAs and digests stay legal. If git is unavailable
the hash check cannot disprove anything and passes rather than blocking the commit. `check_words`
applies the banned-word table to the whole message through `bannedwords.py`; `--rules` says which
file holds it and defaults to the AGENTS.md beside `scripts/`. Imperative mood is not
machine-checkable and stays a convention. Exit 0 clean; exit 1 printing one `commitlint: PROBLEM`
line per violation; argparse exit 2 on usage errors.

Every git call here runs through `gitenv.py`, which strips git's own variables from the
environment. These checks execute inside hooks, where git exports `GIT_DIR`, and that variable
outranks `-C`: inheriting it would silently retarget the call at the repository git is mid-commit
in.

## The five measurement reporters

None of them decides whether the repo is correct. They live in this tree for three reasons: they
must be pure, they must never ship inside the brain image, and they must be tested like everything
else. Each takes sample files written by a live test and prints a report. All five refuse rather
than guess on a sample they cannot read, and each exits 2 printing one `<module>: PROBLEM` line.

- **`contrast.py SAMPLE [SAMPLE ...] [--resamples N] [--seed S]`** reports a live A/B/A timing
  measurement (ADR-0038 decision 22). A live driver measures one variant per process, because a
  variant is a container configuration and changing it recreates the container, so each block
  writes a JSON sample and this reads them back. The first sample is the baseline and every later
  one is compared against it, which is what makes an A/B/A run one command: the middle block is the
  variant under test, the last repeats the first, and the last comparison should span zero. Per
  metric (`ttft` and `wall`, both seconds) it prints each block's mean, median and standard
  deviation, then each comparison as the mean of the per-question mean differences with a 95%
  percentile bootstrap interval, marking an interval that does not span zero, and finally one line
  per question. That last layout matters: the first run had one of six questions at three times the
  mean difference, so the interval alone would have read as a uniform cost it was not. The pairing
  is by question because a turn's time is dominated by its answer's length, which is also why the
  interval is a bootstrap rather than a t interval. The seed is printed with the report.
- **`trailwidth.py CAPTURE [CAPTURE ...] [--resamples N] [--seed S]`** reads captured log text and
  reports the rendered width of the recall trail's `dropped` field, the widest value the brain
  attaches and therefore the value `cortex_core.VALUE_CHARS` is argued against (ADR-0051
  decision 16). Both the message and the field name are registered in `trailcouplings.py` against
  the call that writes them, so a rename in the brain fails `just check` the day it is made. The
  whole line that field sits on is reported beside it, because the per-value bound leaves the line
  itself unbounded. Width is measured from where the shipped formatter's output starts, so a
  capture's own service prefix is not counted. Per capture it prints the count, the lowest and
  highest, the median, and a seeded percentile bootstrap of the mean, then the same for the whole
  line without an interval, then the range over every capture and how many renderings were cut. Any
  cut count above zero means the bound reached a value that ships. A capture whose trail lines were
  written by the packed rendering is refused in a clause saying so.
- **`envelopefloor.py SAMPLE [SAMPLE ...]`** publishes what each variant of the reply-envelope
  measurement did, and refuses when the control variant fell through the floor (ADR-0028
  decisions 11 to 15). The control is the one with no grammar and no appended sentence, read off
  the sample's own `control` field rather than off a name. Two rates describe one run and both are
  published: what a run **stood** is the weaker (the runner accepted it, the reply is not empty, it
  is not the instruction handed back, and on a shape with a declared judge it is not the report
  body handed back either), and what a reply **delivered** is judged against the subtask by
  `envelopejudges.py`, per subtask shape. A shape with no declared judge publishes `stood` alone and
  says so. The floor is nine tenths of a cell's own runs, held per subtask shape, and a cell is
  refused only when its Wilson 95% interval lies wholly under it, so a refusal is a proof. There is
  deliberately no `--floor` setting. `--comma`, `--refusal` and `--naming` choose how a report is
  displayed and never what is published. Exit 1 prints the report with a `refused:` line.
- **`envelopepairs.py SAMPLE SAMPLE [SAMPLE ...]`** counts how many cells two seeded runs of one
  variant produced identically, in `output` and in `tokens`, for every pair of samples given
  (ADR-0050 decision 8). A cell is matched on `question`, `draw` and `seed`. It refuses on a null
  seed, a sample holding one cell twice, two samples holding different cells, and two variants or
  a matched cell given another instruction or body. `trace_budget` is not matched on, because
  comparing a run with that key against one without it is one of the comparisons this count exists
  for. Exit 0 prints one line per pair, naming the cells that differ.
- **`switchtail.py SAMPLE [SAMPLE ...]`** publishes what each tier's chat template rendered for the
  thinking switch, and refuses when that rendering and the cell it predicts disagree (ADR-0050). A
  tier whose template answers the switch by rendering a thought already closed keeps that switch
  under a `response_format`, and one whose answer leaves the thought open does not. The reading is
  taken on the tail, after the last of the request the driver recorded sending, because the failing
  case's two prompts differ by a whole system turn at the front and end identically. A closed
  thought is `</think>` on the native family and `<channel|>` on gemma-4, so every result prints the
  tail it was read from. An unmarked tail that the key left unchanged is the failing case; an
  unmarked tail the key did change is an unrecognized template format and is refused. Nothing is
  published from a constrained cell drawn fewer than five times, nor from one whose control, the
  same request with no switch, never deliberated. The first two lines of the report state the
  sample's `build_info`, `model_path` and `n_ctx`, read once from `GET /props`, so a row copied into
  a record states the engine build, the file and the context it was measured at. The GPU layer count
  is on no route llama-server offers and is typed by hand beside it.
