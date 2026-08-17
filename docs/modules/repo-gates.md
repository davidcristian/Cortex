# scripts/ (`repo-gates`)

**Purpose.** The repo's own tooling, in the tree neither shipped artifact contains: the cross-tree
line cap, the punctuating-dash ban, the cross-language constant check, the compose bind-mount
check, the backlog gate, the Rust coverage threshold, the CI path classifier, the
commit-message style hook,
and, since 2026-08-09, the one module here that gates nothing, the interval a live measurement
reports. What they have in common is not that each is a gate; it is that each is pure Python that
belongs to neither the brain nor the body and is gated exactly like both. A standalone uv project
(not a brain workspace member, per ADR-0002).

**Public contract** (all are CLIs, with `linecap.py`, `dashcheck.py`, `crosscheck.py`,
`bindcheck.py`, `backlogcheck.py` and `coverage_gate.py` invoked by `just` recipes, `ci_paths.py`
by the CI
workflow, `commitlint.py` by the commit-msg pre-commit stage, `contrast.py` by `just turn-cost`;
each also exposes a pure, unit-tested core function). Seven modules here have no CLI of their own,
each split out under the line cap and each named for what it holds: `couplings.py` and
`overlaycouplings.py` are the two halves of `crosscheck.py`'s registry, `values.py` is the value
forms that scan compares on, `composemounts.py` is `bindcheck.py`'s compose reader, and
`backlog.py`, `backlogindex.py` and `backloganchors.py` are the three `backlogcheck.py` reads a
backlog through: the task-file grammar, the index renderer, and the anchors an index offers with
every pointer in the repo aimed at one.

- `linecap.py [--root DIR] [--max-lines N]` implements AGENTS.md gate 1. Scans
  `*.py`/`*.rs`/`*.ts`/`*.tsx` under `--root` (default `.`), all three gated toolchains
  since the ADR-0011 line-cap addendum, counting ALL lines (code, comments, blanks; cap
  default 300). Stylesheets, markup and `proto/body.proto` are outside the cap by that same
  addendum. Skips dir components `.git`, `.venv`, `.claude`, `target`, `node_modules`,
  `__pycache__`, `.pytest_cache`, `.ruff_cache`, `dist`, `coverage`, `tests`, `_generated`
  (the generated-code marker), and test-named files (`test_*.py`, `*_test.py`,
  `conftest.py`, `*_test.rs`, `*.test.ts`, `*.test.tsx`, `test-setup.ts`, the last three
  being what `body/app/vite.config.ts` collects and sets up). `*.d.ts` is NOT exempt.
  Directory symlinks are not traversed (deliberate: no
  cycles, no escapes outside the root); a candidate that is not a regular file after
  following symlinks (e.g. a dangling editor-lockfile symlink) is skipped.
  Exit 0 with a summary line; exit 1 printing `path: N lines (cap M)` per violation;
  exit 2 if `--root` is not a directory or a source file cannot be read.
- `dashcheck.py [--root DIR]` implements the no-dash-as-punctuation rule (ADR-0026).
  Scans EVERY text file under `--root` (default `.`), not just `*.py`/`*.rs`, because the
  rule covers docs and comments alike. Flags U+2014 EM DASH and U+2013 EN DASH anywhere,
  spaced or not, since a range takes a plain ASCII hyphen. Deliberately silent on U+2212
  MINUS SIGN (arithmetic), and on ASCII `--` (the repo's inline-reason idiom, which the gate-2
  escape-hatch rule effectively requires; commit messages are stricter and `commitlint.py`
  bans it there). Skips the same directory components as `linecap.py` minus `tests` and
  `_generated`, since prose in a test or a generated stub is still prose, and
  `test_skipped_dirs_match_dashcheck_plus_tests_and_generated` holds the two lists to that
  sentence rather than leaving it to be believed; binary files are
  detected and skipped. A line carrying `dashcheck: allow` plus a reason is exempt, for a
  dash that means rather than punctuates. Exit 0 with a summary; exit 1 printing
  `path:line: kind: text` per violation; exit 2 if `--root` is not a directory or a file
  cannot be read.
- `crosscheck.py [--root DIR]` ties the values this repo spells in more than one place, because
  both sides of a seam must hold the same one and neither toolchain can import the other's
  (ADR-0029 cross-language-constant addendum and its 2026-08-08 widening). The scan is all of the
  logic; `couplings.py` and `overlaycouplings.py` are all of the data, one entry per value: a
  label, the reason its places must agree (printed with any failure), its `Site`s, an optional
  `relation`, and optional `mentions`. The registry is written in two files and read as one,
  `crosscheck.CONSTANTS` being `SEAM_COUPLINGS` followed by `OVERLAY_COUPLINGS`: the first file
  holds the vocabulary every entry is written in plus the couplings that tie the body to the brain,
  the second the ones that tie the overlay's TypeScript to its own stylesheet, which is where the
  entries were already accumulating when the one file outgrew the cap. Nothing in the scan depends
  on which half an entry sits in. `values.py` is the third piece and the one neither of the others
  is: it reduces a right-hand side to a comparable value and says whether a constant's readings
  hold together, so the scan finds declarations and that module judges them.
  **A `Site` declares the value** (a repo-relative path plus the identifier declared in it) and is
  read and compared. **A `Mention` spends it without declaring it** (a path plus a template
  carrying `{value}`): the scan renders the agreed value into the template and requires the result
  to appear in the file **as a token of its own**, `bounded()` guarding whichever of the needle's
  two edges is itself a word character. That is not circular, since the template carries the shape
  and the site carries the value, and it is what lets the gate reach a key spelled inside a shell
  string, a custom property a stylesheet reads back with `var(...)`, and a bare literal a component
  compares against, with no promotion to a named constant first.
  **A mention may render a NAME instead of, or beside, the value.** Where the far side names the
  value rather than restating it, a rendered value reaches the declaration and never the spend:
  `overlay.css` writes `--roll: 300ms` once and pays it as `var(--roll)` twice, and only the first
  of those carries a number. So `Mention.name` is the name that far side spends it under and
  `{name}` renders it, which makes the pair two mentions of one entry, `{name}: {value}ms;` over
  the declaration and `var({name})` over the spends. A mention carries a name exactly when its
  template renders one (either half alone is dead data and a fault), and the registry refuses a
  name pinned as a spend that no mention of the same entry renders a value under, which would hold
  the name while quietly dropping the value. Two properties live in this shape, `--roll` and
  `--ease`, being the two the overlay's TypeScript declares the value of rather than the name.
  **Bounded, and written to cover the whole of what it pins.** Bare containment passed on two real
  violations: a value that is a prefix of the one written down (`5005` inside `50051`), which the
  bound now refuses, and a published `host:container` port pair whose host half alone carried the
  needle, which is a template question rather than a matcher one, so the compose publish is
  registered as `"127.0.0.1:{value}:{value}"` and the healthcheck dial beside it as its own
  mention.
  **Counted where the occurrences are one set.** A mention is a presence check unless it carries
  `occurrences`, so a file spending the value twice and losing one of them passes by default,
  which is what a half applied rename looks like. `occurrences` pins an EXACT number of bounded
  matches rather than a floor, because a floor cannot notice the far side has grown past it and so
  widens itself by however much the tree drifted; a count below 1 is refused, zero being a mention
  asking the value to be absent. It is opt in, and the survey that set it is in the ADR: three of
  the seventeen registered mentions are counted, `Message.tsx` at 2 (the `className` and the
  `aria-label` of one chip), `overlay.css`'s `:not([{value}="0"])` at 2 (the two section share
  caps, whose handover is symmetric or nothing), and `overlay.css`'s `var(--roll)` at 2 (the two
  rules that must land WITH a roll, which is the set the entry's own reason names), while the bare
  `[{value}` mention stays a presence check because its three rules are the sum of two unrelated
  features and `var(--ease)` stays one because 52 transitions across unrelated features ride that
  curve. Every mention that occurs once is left unpinned, a count of one saying nothing a presence
  check does not.
  **`Relation`** is `EQUAL` by default; `ORDERED` holds an entry's sites to non-decreasing order
  in registry order, for a bound that must sit under another rather than match it. An ordering
  compares numbers only (a string under one is a fault), and it may carry no mentions, there being
  no single value to spell. `MEMBER` is the third and it reads registry order too: every site but
  the last must declare a value the last site's collection carries, which is the shape of a value
  one tree produces and another accepts a set of (the body's `CAPTURE_MIME` inside the brain's
  `ALLOWED_MIME_TYPES`, where the two are neither equal nor one under the other). The last site
  declaring a lone value rather than a collection is a fault, since `in` over two strings would
  quietly answer about substrings; like an ordering, it may carry no mentions.
  **No master:** the sites are compared with each other, not against a declared value, so
  editing either side alone fails and a deliberate change is a change to all of them.
  `proto/body.proto` is not the source: protobuf has no constant, so a value could only sit
  there as a comment, which is one more uncoupled copy. Values are compared after reduction,
  so `6291456` and `6 * 1024 * 1024` tie; the three forms that reduce are a product of integer
  literals, a plain double-quoted string, and a one-line `frozenset` of those strings, which is
  how this repo spells an allow-list and is what a membership is decided against (a set literal
  is mutable and a multi-line spelling never reaches the reducer, a declaration being captured one
  line at a time). `DECLARATIONS` holds one declaration syntax
  per language (`.py`, `.rs`, `.ts`), matching module-level and item-level constants only: the
  Python and TypeScript forms are anchored at column 0, so an indented `const` is a local and not
  a second declaration of the module's constant. A mention needs no declaration syntax, so its
  file may be any text at all (`.css`, `.yml`, `.tsx`).
  **Fails closed by design**, because a scan that cannot find its constants would agree with
  itself forever: a missing file, an unreadable or non-UTF-8 one, an unknown suffix, a name
  that is absent, one declared twice, a value it cannot reduce, a mention whose rendered needle is
  absent or found a different number of times than it pins or whose template renders neither
  `{value}` nor `{name}` or renders a name it does not carry or carries one it renders nowhere
  or pins a count below 1, a name pinned as a spend that no mention pays a value under, and a
  registry entry naming no declaring site or
  fewer than `MIN_PLACES` (2) places are each a fault, never a skip. Exit 0 with a summary; exit 1
  printing `label: detail` per fault; exit 2 if `--root` is not a directory.
- `bindcheck.py [--root DIR]` holds every compose bind mount to landing somewhere git
  accounts for (ADR-0026 bind addendum). The rule, stated in the module's own docstring: a
  bind source must resolve **outside** the repo (an absolute path, or an expansion with no
  relative default, so the user's own disk), or onto a path git **tracks** (an input the repo
  ships, which compose finds rather than creates), or onto a path git **ignores** (an output a
  container writes). It is deliberately NOT "every default must be gitignored", which would be
  false of `./docker/postgres/init.sql`. Git answers both questions (`ls-files`, `check-ignore`),
  with git's own `GIT_*` variables stripped for the same reason `commitlint.py` strips them, and
  `check-ignore` is asked with a trailing slash because compose materializes a **directory** and
  a directory-only pattern (`models/`) does not match a bare path. A relative source is resolved
  against BOTH project directories compose can pick, the repo root (what the `just` recipes pass)
  and the compose file's own directory (what a bare `docker compose -f docker/...` uses), which
  is why the repo's ignore entries for these paths are unanchored; an anchored `/models/` is
  reported. **Both questions are asked per landing**, never once for the mount: a source can name
  an input the repo ships under one project directory and nothing at all under the other, and it
  is the second landing that a compose run creates. That is why `.gitignore` carries
  `docker/docker/`, where `./docker/postgres/init.sql` and its two neighbours resolve when the
  project directory is `docker/`. Compose files are found by name anywhere under `--root` (stem `docker-compose`/
  `compose`, suffix `.yml`/`.yaml`), skipping the vendored directory components, so a new override
  is covered wherever it is added. **Fails closed**: no compose file at all, a mount entry the
  reader refuses, a source that cannot be reduced, and a git that cannot run are each a fault,
  never a skip. Exit 0 with a summary; exit 1 printing `path:line: detail` per fault; exit 2 if
  `--root` is not a directory or the scan could not run at all.
- `composemounts.py` is `bindcheck.py`'s reader and has no CLI. `read_mounts(text)` returns one
  `Mount(line, source)` per bind mount a compose file declares, skipping named volumes (long-form
  `type:` in `NON_BIND_TYPES`, short-form sources without a `PATH_PREFIXES` prefix) and the
  top-level `volumes:` mapping. It is a line walk, not a YAML parse, because these gates are
  stdlib-only; it stays honest about that by raising `ComposeReadError` on every shape it was not
  taught (an inline `volumes: [...]`, a mount with no `type`, an unknown type, a bind with no
  `source`, a short-syntax entry carrying an expansion, a flow-style entry opening with `{` or
  `[`, a stray line inside a block). The one YAML rule it leans on is that a mapping needs a space
  after its colon, which is what tells `type: bind` from the short-syntax scalar
  `redis-data:/data`. The second is that a sequence may be written **flush**, its items at the
  indent of the key they belong to, which compose accepts and this reader now walks: a block ends
  at a line shallower than its key, or at one beside the key that is not a list item.
- `backlogcheck.py [--root DIR] [--write]` holds each backlog index to the task files it
  describes (ADR-0039). Without `--write` it checks, which is what `just check-backlog` runs;
  with `--write` it regenerates each index, which is what `just backlog` runs. That split is the
  whole mechanism and it is `cargo fmt --check` pointed at a backlog: the index cannot be edited
  into disagreement with the tasks, because the only supported way to change it is to change a
  task file and regenerate. Five things fail. A task file outside the layout (a name that is not
  `NNN-slug.md`, a missing, duplicated or unknown field, a status outside the grammar, a title
  restating its own status, a number already used, or one of the two waiting states not naming
  its trigger). A relative link in a task file or an index that does not resolve. **A fragment
  aimed at a heading a backlog index does not render**, which is the same link's other half and
  the half a rename breaks silently, checked since the ADR-0039 anchor addendum. An index whose
  generated block is stale, missing or hand-edited. A `tasks/` directory holding anything that is
  not a task file. Exit 0 with one count line per backlog; exit 1 printing one problem per line;
  exit 2 if `--root` is not a directory.
- `backlog.py` is the task-file grammar and has no CLI: `load(directory, kind)` parses every
  `NNN-slug.md` into a `Task`, raising `TaskFileError` naming the file and what is wrong with it.
  A `Status` is parsed from a closed grammar and answers `is_open`, `is_standing` and the index
  `bucket` it files under, so nothing downstream re-derives a state from prose.
- `backlogindex.py` renders the generated half of an index and has no CLI. `render(tasks,
  group_word)` returns the whole block, markers included: the counted headline, the open set
  under one heading per bucket, the standing items, then the roll call under one `### <group>`
  heading per area or sitting. `splice(existing, block)` puts it back between the markers,
  raising `ValueError` when a marker is missing or out of order. Nothing in that block is typed
  by hand, so a count in it cannot disagree with the files it counts. One count is a sentence
  rather than a number, the tally of waiting tasks whose trigger nobody recorded, and it renders
  in the singular at one, that being the reading the pass which finishes the job produces.
- `backloganchors.py` is the anchor half of the link check and the only part of this gate that
  reads outside the backlog. `anchors(text)` returns every anchor a document offers, by the slug
  rule a markdown renderer uses (lowercase, drop every character that is not a word character, a
  space or a hyphen, spaces to hyphens, a repeated heading numbered from its second occurrence),
  with a `#` inside a fenced block not counted as a heading. `check(root, indexes)` walks every
  markdown file under `--root`, skipping the directory components `dashcheck.py` skips for the
  reason that gate gives, and reports any fragment aimed at one of those indexes that names no
  heading it renders; a pointer with no path is aimed at the document it is written in, which is
  how an index's links to its own hand-written sections are covered. **The anchor set comes from
  the spliced index**, the hand-written halves around the freshly rendered block, and never from
  the committed file: a stale index is then judged as the document it is about to become, and its
  staleness stays one problem instead of a hundred. Sources are repo-wide and targets are not.
  Most pointers at these anchors live in decision records and runbooks, which are exactly the
  readers a rename strands, so the scan reads them; a fragment aimed at any other document is out
  of scope, that being a heading set per document in the repo and a wider scan.
- `coverage_gate.py PATH [--rustc TEXT] [--llvm-cov TEXT]` reads a
  `cargo llvm-cov --json --summary-only` export, requires exactly one `data[]` entry, and gates
  each of `data[0].totals.{lines,regions,branches}` on `covered == count` (the producer's
  `percent` is never trusted; displayed percentages are recomputed). A metric with
  `count == 0` passes vacuously (with a printed note). Malformed/missing/non-UTF-8
  input → typed error on stderr, exit 1, no verdict printed. Exit 0 only when every check passes.
  **This is the whole coverage verdict, not the branch half of it** (ADR-0002 single-verdict
  addendum): cargo-llvm-cov's own `--fail-under-lines/-regions` came off the measurement, since
  with the report diverted by `--json --output-path` they exit 1 printing nothing at all, which
  pre-empted this gate with a mute failure while restating a threshold it already enforced.
  It also attributes the numbers it judges. The export records its own writer in
  `cargo_llvm_cov.version` beside the llvm export format's `version`; both are **required**, and an
  export that will not name its writer is refused. `check-body` additionally passes what it probed:
  `--rustc` is relayed into the verdict, the compiler being absent from the export, and
  `--llvm-cov` must appear in the export's own record, so an export the running tool did not write
  fails the gate however good its numbers are. Neither version is pinned on either side
  (ADR-0002 toolchain-print addendum), which is why a verdict has to carry them.
  Verdicts print in order: the attribution lines (`measured by ...`), then one `PASS`/`FAIL` line
  per metric.
- `ci_paths.py` implements AGENTS.md gate 3 / ADR-0006. Decides which toolchain CI jobs must run
  for a set of changed files. Reads newline-separated repo-relative paths (the output of
  `git diff --name-only`) on stdin; blank lines are ignored. Each path is classified by
  ordered rules, first match wins (the normative rule list lives in ADR-0006); the
  result is the union over all paths. Writes exactly three `GITHUB_OUTPUT`-format lines
  to stdout, in order: `python=true|false`, `rust=true|false`, then `overlay=true|false`
  (the overlay = the `body/app/` React tree, gated by `check-overlay`; its Tauri shell
  subtree `body/app/src-tauri/` is Rust and is carved back to `rust`), and nothing else.
  Logs one `ci-paths: PATH -> VERDICT` line per path to stderr so CI logs show why a job
  ran. Empty input yields all three `false`. Unmatched paths fail closed to ALL three
  (unknown means over-test, never under-test). Always exits 0, because classification has no
  failure mode.
- `commitlint.py MESSAGE_FILE [--repo DIR]` is the machine-checkable half of the AGENTS.md
  commit rules, run at the commit-msg stage next to conventional-pre-commit. Checks the
  header (first non-comment line): ≤ 72 chars, lowercase subject, no trailing period. A
  header that is not Conventional-Commits-shaped passes silently (structure errors are the
  other hook's to report); `Merge `/`fixup! `/`squash! `/`amend! ` headers are exempt, body
  rules included, because that wording is git's and not the author's. Every line BELOW the
  header must wrap at 72 (`MAX_BODY_WIDTH`, the same number the header is capped at, checked
  separately so one long subject is one complaint): a line past it that could have been wrapped
  fails, and `too_wide` exempts one whose longest word alone is over the wrap, since a URL, a
  path, or a long identifier has nowhere to break and demanding a rewrite that cannot exist
  would train authors to ignore the gate. Four 73-character lines reached master before this
  landed, which is what it was added for. `classify_lines` is the one walk that decides a
  line's KIND, pairing each line with whether it is a paste and reporting any fence left open
  (ADR-0026's two 2026-08-09 addenda): a line between two fences (` ``` ` or `~~~`, an info
  string included, the markers themselves counted as part of the block) and a line whose first
  token is a bare `$` are pastes, and moving a newline inside one changes what it says. Line 1
  is the header, prose by construction, so no message exempts its own subject. A fence left
  open at the end of the walk is a violation naming the line that opened it, since otherwise
  one stray fence exempts every line after it while the gate still exits 0. A leading indent is
  deliberately NOT a signal: all 9 four-space-indented lines in this repo's history are prose. A
  `BREAKING CHANGE:` footer is not exempt either, being prose over a token no newline harms.
  **A paste is exempt from the wrap and from the dash ban, and from nothing else**, the split
  being what each rule is for: those two are about the text as typed and have no remedy inside
  a paste (a reflowed command and a stripped `--` both say something else), while the
  volatile-reference ban and the hash check are about the message still reading correctly after
  what it points at moves, which does not care who typed the pointer and which keeps its remedy,
  `git show <sha>` carrying everything the paste carried. So a fenced
  `cargo llvm-cov -- --nocapture` passes and a fenced `git show` of a resolving hash does not.
  Across the WHOLE
  message (subject and body) it also bans a dash used as punctuation (em dash, en dash,
  spaced ASCII `--`, since a message is pure prose) and volatile references: a slice
  number, a decision-record number, the roadmap, or a numbered assumption/increment/gate/
  decision/audit. Hex tokens are resolved against `--repo` (default `.`) with `git
  cat-file`, so ONLY a hash that really is a commit is reported: a rewrite invalidates it,
  while action SHAs and digests stay legal. If `git` is unavailable the hash check cannot
  disprove anything and passes rather than blocking the commit. Imperative mood is not
  machine-checkable and stays convention. Exit 0 clean; exit 1 printing one
  `commitlint: PROBLEM` line per violation; argparse exit 2 on usage errors.
  That `git` call, and every one its tests make, runs with git's own variables stripped
  from the environment: these gates execute inside hooks, where git exports `GIT_DIR`, and
  that variable OUTRANKS `-C`. Inheriting it silently retargets the call at the repository
  git is mid-commit in, which answered the hash question about the wrong object database
  and, in the tests, staged a fixture file into the in-flight commit's own index.

- `contrast.py SAMPLE [SAMPLE ...] [--resamples N] [--seed S]` is the one module here that gates
  nothing: it is the reporting half of a live measurement, and it lives in this tree because it
  must be pure, must never ship inside the brain image, and must be covered like everything else
  (ADR-0038 harness addendum). A live block driver measures ONE arm per process, since an arm is a
  container configuration and changing it recreates the container, so each block writes a JSON
  sample and this reads them back. **The first sample is the baseline and every later one is
  contrasted against it**, which is what makes an A/B/A run one command: the middle block is the
  arm under test, the last repeats the first, and the last contrast is a null whose interval ought
  to span zero. Per metric (`ttft`, `wall`, both seconds) it prints each block's unblocked mean,
  median and standard deviation, then each contrast as the mean of the per-question mean
  differences with a 95% percentile bootstrap interval, starring an interval that does not span
  zero, and finally the blocking unit itself, one line per question. That last layout is not
  decoration: the harness's first run had one of six questions carrying three times the mean
  difference, so an interval read alone would have been read as a uniform cost it was not.
  The pairing is **by question** because a turn's time is dominated by its answer's length,
  and the resampling unit is therefore the question, which is why the interval is a bootstrap
  rather than a t interval: n is the number of questions and turn times are right-skewed. The seed
  is printed with the report, so the arithmetic is reproducible without the GPU; the run that
  produced the samples is not. Refuses rather than guesses on a malformed sample, on two blocks
  that asked different questions, on a single sample, and on a non-positive resample count. Exit 0
  printing the report; exit 2 printing one `contrast: PROBLEM` line; argparse exit 2 on usage.

**Invariants.**
- stdlib-only modules; pure cores (`scan`, `evaluate`/`check`, `classify`, `report`) unit-tested
  to 100% line+branch; the only coverage pragmas are the `__main__` guard lines.
- This suite runs **shuffled under a fixed seed**, `--randomly-seed=7919` in `addopts`, as all
  three other gated suites do under their own (ADR-0002 shuffle addendum, and its rust-shuffle
  addendum for the fourth). The order is therefore not
  the collection order and is still the same order twice, so a test that depends on a sibling
  fails here reproducibly rather than intermittently. Two consequences for anyone working in this
  tree. The seed is frozen: changing it reshuffles the suite and throws away every draw it has
  already survived, and it differs from the brain's, the overlay's and the Rust workspace's on
  purpose, four
  independent numbers rather than one value `crosscheck.py` should tie. And `-p no:randomly` now
  exits 2 on the seed it leaves unrecognized rather than silently disabling nothing, which is what
  the flag used to do here; the sweep over other orders is `just shuffle [seed]`.
- `crosscheck.py`'s registry is checked against the real trees by its own suite
  (`test_the_repo_itself_is_tied`), so `check-scripts` catches a drift even when
  `check-crosscheck` is not the recipe that runs. Registering a constant in a language
  `DECLARATIONS` does not know, or a mention whose template renders nothing the registry fills, or
  one whose name and whose `{name}` do not both appear, or an entry whose places are all one
  language, is refused by that suite too. It used to refuse an entry
  confined to one top-level tree; the overlay and its stylesheet are one tree and two languages,
  so suffix replaced tree when mentions landed. Two more invariants guard the widening itself: the
  registry must exercise every `Relation` member and both kinds of place, since a comparator no
  entry uses is a gate that cannot fail. `test_the_registry_pins_at_least_one_occurrence_count`
  and `test_the_registry_spends_at_least_one_rendered_name` hold the two newest fields to the same
  rule, a field no entry sets being a dead wire.
- `bindcheck.py` does the same (`test_the_repo_itself_is_clean`), with a guard on the guard:
  `test_the_repo_really_declares_binds_for_this_gate_to_have_checked` fails if the reader ever
  finds fewer than six defaulted bind sources under `docker/`, so the clean verdict cannot go
  vacuously green on a reader that stopped matching.
- `backloganchors.py` is held to both halves of that same pattern:
  `test_the_repo_itself_offers_every_anchor_aimed_at_it` runs the anchor check over the real
  tree, and `test_the_repo_really_aims_pointers_at_both_indexes_from_outside_the_backlog` fails
  if either index ever stops being pointed at from outside its own directory, the population a
  backlog-only scan would have missed being the one that guard exists to keep in the input.
- The exclusion lists above are the single definition of "non-test source file" and
  "generated code" for the cap. Change them only with an ADR update.
- `dashcheck.py`, `commitlint.py`, and their tests spell the dashes as `\uXXXX` escapes
  rather than literals, so the gates pass the rule they enforce. A literal would make the
  gate flag itself.
- `ci_paths.py` runs under a plain `python3` on a GitHub runner **before** any `uv
  sync`: it must never grow a third-party import. Its `RULES` table and the rule list
  in ADR-0006 are the same normative list, so change them together.

**Dependencies.** Python stdlib; dev-only: pytest, pytest-cov, pyright, ruff.
