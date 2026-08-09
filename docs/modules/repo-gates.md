# scripts/ (`repo-gates`)

**Purpose.** The repo's own gate tooling: the cross-tree line cap, the punctuating-dash
ban, the cross-language constant check, the compose bind-mount check, the Rust branch
coverage threshold, the CI path classifier, and the commit-message style hook. A standalone
uv project (not a brain workspace member, per ADR-0002), gated exactly like all other Python.

**Public contract** (all are CLIs, with `linecap.py`, `dashcheck.py`, `crosscheck.py`,
`bindcheck.py` and `coverage_gate.py` invoked by `just` recipes, `ci_paths.py` by the CI
workflow, `commitlint.py` by the commit-msg pre-commit stage; each also exposes a pure,
unit-tested core function). `composemounts.py` is the one module that is not a CLI: it is
`bindcheck.py`'s compose reader, split out under the line cap.

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
  logic; `couplings.py` is all of the data and holds `CONSTANTS`, one entry per value: a label,
  the reason its places must agree (printed with any failure), its `Site`s, an optional
  `relation`, and optional `mentions`.
  **A `Site` declares the value** (a repo-relative path plus the identifier declared in it) and is
  read and compared. **A `Mention` spends it without declaring it** (a path plus a template
  carrying `{value}`): the scan renders the agreed value into the template and requires the result
  to appear in the file **as a token of its own**, `bounded()` guarding whichever of the needle's
  two edges is itself a word character. That is not circular, since the template carries the shape
  and the site carries the value, and it is what lets the gate reach a key spelled inside a shell
  string, a custom property a stylesheet reads back with `var(...)`, and a bare literal a component
  compares against, with no promotion to a named constant first.
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
  asking the value to be absent. It is opt in, and the survey that set it is in the ADR: two of the
  fourteen registered mentions are counted, `Message.tsx` at 2 (the `className` and the
  `aria-label` of one chip) and `overlay.css`'s `:not([{value}="0"])` at 2 (the two section share
  caps, whose handover is symmetric or nothing), while the bare `[{value}` mention beside it stays
  a presence check because its three rules are the sum of two unrelated features. Every mention
  that occurs once is left unpinned, a count of one saying nothing a presence check does not.
  **`Relation`** is `EQUAL` by default; `ORDERED` holds an entry's sites to non-decreasing order
  in registry order, for a bound that must sit under another rather than match it. An ordering
  compares numbers only (a string under one is a fault), and it may carry no mentions, there being
  no single value to spell.
  **No master:** the sites are compared with each other, not against a declared value, so
  editing either side alone fails and a deliberate change is a change to all of them.
  `proto/body.proto` is not the source: protobuf has no constant, so a value could only sit
  there as a comment, which is one more uncoupled copy. Values are compared after reduction,
  so `6291456` and `6 * 1024 * 1024` tie; the two forms that reduce are a product of integer
  literals and a plain double-quoted string, and `DECLARATIONS` holds one declaration syntax
  per language (`.py`, `.rs`, `.ts`), matching module-level and item-level constants only: the
  Python and TypeScript forms are anchored at column 0, so an indented `const` is a local and not
  a second declaration of the module's constant. A mention needs no declaration syntax, so its
  file may be any text at all (`.css`, `.yml`, `.tsx`).
  **Fails closed by design**, because a scan that cannot find its constants would agree with
  itself forever: a missing file, an unreadable or non-UTF-8 one, an unknown suffix, a name
  that is absent, one declared twice, a value it cannot reduce, a mention whose rendered needle is
  absent or found a different number of times than it pins or whose template carries no `{value}`
  or pins a count below 1, and a registry entry naming no declaring site or
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
- `coverage_gate.py PATH` reads a `cargo llvm-cov --json --summary-only` export,
  requires exactly one `data[]` entry, and gates each of
  `data[0].totals.{lines,regions,branches}` on `covered == count` (the producer's
  `percent` is never trusted; displayed percentages are recomputed). A metric with
  `count == 0` passes vacuously (with a printed note). Malformed/missing/non-UTF-8
  input → typed error, exit 1. Exit 0 only when all three metrics pass.
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
  landed, which is what it was added for. Across the WHOLE
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

**Invariants.**
- stdlib-only modules; pure cores (`scan`, `evaluate`/`check`, `classify`) unit-tested
  to 100% line+branch; the only coverage pragmas are the `__main__` guard lines.
- `crosscheck.py`'s registry is checked against the real trees by its own suite
  (`test_the_repo_itself_is_tied`), so `check-scripts` catches a drift even when
  `check-crosscheck` is not the recipe that runs. Registering a constant in a language
  `DECLARATIONS` does not know, or a mention whose template carries no `{value}`, or an entry
  whose places are all one language, is refused by that suite too. It used to refuse an entry
  confined to one top-level tree; the overlay and its stylesheet are one tree and two languages,
  so suffix replaced tree when mentions landed. Two more invariants guard the widening itself: the
  registry must exercise both `Relation` members and both kinds of place, since a comparator no
  entry uses is a gate that cannot fail. `test_the_registry_pins_at_least_one_occurrence_count`
  holds the newest field to the same rule, a field no entry sets being a dead wire.
- `bindcheck.py` does the same (`test_the_repo_itself_is_clean`), with a guard on the guard:
  `test_the_repo_really_declares_binds_for_this_gate_to_have_checked` fails if the reader ever
  finds fewer than six defaulted bind sources under `docker/`, so the clean verdict cannot go
  vacuously green on a reader that stopped matching.
- The exclusion lists above are the single definition of "non-test source file" and
  "generated code" for the cap. Change them only with an ADR update.
- `dashcheck.py`, `commitlint.py`, and their tests spell the dashes as `\uXXXX` escapes
  rather than literals, so the gates pass the rule they enforce. A literal would make the
  gate flag itself.
- `ci_paths.py` runs under a plain `python3` on a GitHub runner **before** any `uv
  sync`: it must never grow a third-party import. Its `RULES` table and the rule list
  in ADR-0006 are the same normative list, so change them together.

**Dependencies.** Python stdlib; dev-only: pytest, pytest-cov, pyright, ruff.
