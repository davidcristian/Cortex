# The thirteen cross-tree scans

These are the checks `just check` runs before any per-toolchain work, and the ones CI runs on every
change whatever files it touched. Each reads several trees at once, which is why none of them can
live inside the brain's or the body's own suite. The module list and the shared readers are in
[repo-checks.md](repo-checks.md).

**What they all share.** Exit 0 prints a summary line stating what the walk read after every
exclusion, so a passing run cannot be equally true of a scan that read nothing. Exit 1 prints one
problem per line, usually `path:line: detail`. Exit 2 means the scan could not run: `--root` is not
a directory, an input could not be read or decoded, or the reader met a syntax it was not taught.
Nothing is ever skipped quietly. Every scan takes `--root DIR`, defaulting to the current directory.

## `linecap.py`

Two rules over one walk, both counting every line including comments and blanks.
`--max-lines` (default 300) caps each `*.py`, `*.rs`, `*.ts` and `*.tsx` file.
`--document-max-lines` (default 250) caps each `*.md` file. `EXEMPTIONS` leaves out the two backlog
indexes `just backlog` writes, and each is exempt only while it still contains the comment that
recipe puts above its generated block, so an index somebody starts maintaining by hand stops being
exempt. Stylesheets, markup and `proto/body.proto` are outside the cap by ADR-0011 decision 12.

Files come from `treewalk.walk_files`, so the scan skips the eleven directory names in
`skippeddirs.SKIPPED_DIRS` plus two of its own, `tests` and `_generated`, and every test-named file
(`test_*.py`, `*_test.py`, `conftest.py`, `*_test.rs`, `*.test.ts`, `*.test.tsx`, `test-setup.ts`).
`*.d.ts` is not exempt, directory symlinks are not followed, and anything that is not a regular
file is skipped. Exit 1 prints `path: N lines (cap M)`. Exit 2 also covers an exemption that no
longer applies, and either rule measuring no file at all.

## `dashcheck.py`

The no-dash-as-punctuation rule (ADR-0026). It reads every text file in the working tree minus what
git ignores, so a file staged but not committed is read while generated schemas and coverage
exports are not. Git is asked once for the ignored paths and a wholly ignored directory is pruned
rather than descended, which keeps the walk out of the model files under a bind target. `--root`
must therefore be a git working tree, and a git that cannot answer is a failure.

It reports U+2014 EM DASH and U+2013 EN DASH anywhere, spaced or not, since a range takes a plain
ASCII hyphen. It is deliberately silent on U+2212 MINUS SIGN and on ASCII `--`, which this repo
uses for an inline reason; commit messages are stricter and `commitlint.py` reports it there.
Binary files are detected and skipped, and a line containing `dashcheck: allow` plus a reason is
exempt. Exit 1 prints `path:line: kind: text`.

## `prosecheck.py`

The part of the Prose section of AGENTS.md a machine can check (ADR-0040 decisions 11 and 12): a
word from that file's banned-word table, a docstring over three lines, and a comment block over
three lines. With no PATH it checks the whole root. A PATH that is a file is checked even when git
ignores it; a directory is walked with `treewalk.walk_files` minus `_generated` and what git
ignores, so `--root` must be a git working tree.

It reads prose and nothing else: markdown outside code fences, Python docstrings, and comments in
Python, Rust, TypeScript, CSS, protobuf, YAML, TOML, shell, SQL, the Dockerfiles and the justfile.
String literals, identifiers, code spans, link targets, URLs and the rows of the table itself are
never read. A word matches whole and in any case, and one line break may split a phrase.

A comment block is a run of lines holding only comments: a line holding code ends it and a blank
line does not, and a line counts unless its text without the comment markers is empty or is a tool
directive such as `noqa` or `pragma`. `EXEMPTIONS` leaves two docstrings alone with a reason each,
`registry.py`'s module docstring and the email server's `@server.tool` descriptions, and an
exemption naming a file or a docstring that is gone is a failure.

## `crosscheck.py`

Values this repo writes in more than one place, compared with each other, because both sides of the
body↔brain boundary must use the same one and neither toolchain can import the other's (ADR-0042).
The scan is all of the logic and the `*couplings.py` files are all of the data, one entry per value:
a label, the reason its places must agree (printed with any failure), its `Site`s, an optional
`relation` and optional `mentions`.

`registry.py` is the only module that lists the parts, so a new part is a data file plus one line
there. `crosscheck.CONSTANTS` is `SEAM_COUPLINGS`, `ENDPOINT_COUPLINGS`, `SHIPPED_COUPLINGS`,
`CAPTURE_COUPLINGS`, `BOUNDS_COUPLINGS`, `SUBAGENT_COUPLINGS`, `MODELHOST_COUPLINGS`,
`LEVER_COUPLINGS`, `IMAGE_COUPLINGS`, `EMAIL_COUPLINGS`, `FIXTURE_COUPLINGS`, `OVERLAY_COUPLINGS`,
`LOG_COUPLINGS` and `TRAIL_COUPLINGS`, in that order. Each part is named for its subject, and its
own module docstring says which values it covers.

- **A `Site` declares the value**: a repo-relative path plus an identifier declared in that file.
  The scan reads text and imports nothing, so a module-private name is registrable and the file need
  not be one `just check` compiles. A name that is absent, declared twice, or whose value cannot be
  reduced is a failure.
- **A `Mention` uses the value without declaring it**: a path plus a template containing `{value}`.
  The rendered text must appear in that file as a whole token, which reaches a key inside a shell
  string, a custom property a stylesheet reads back with `var(...)`, and a bare literal a component
  compares against. A template may render `{name}` instead of or beside the value, for a far side
  that uses the name rather than the number.
- **Counted only where the occurrences are one set.** A mention is a presence check unless it gives
  `occurrences`, which requires an exact number of matches. It is used where one file writes the
  same value twice for two different readers, so losing one leaves the file stating two answers.
- **Compared after reduction, with no master.** Sites are compared with each other, never against a
  declared source, so editing one side alone fails. `6291456` and `6 * 1024 * 1024` are equal, `5`
  and `5.0` are not, because a decimal reduces to its digits rather than to a number, and a boolean
  reduces to its word. `Spelling.WHOLE` and `Spelling.LOWERED` rewrite one value for a far side
  whose syntax cannot take it as written, computed rather than typed into the registry.
- **`Relation`** is `EQUAL` by default. `ORDERED` requires the entry's sites to be non-decreasing
  in registry order, over integers only. `MEMBER` requires every site but the last to declare a
  value the last site's collection contains.
- **A missing search text says whose literal stopped matching.** The result reports whether the file
  still contains this entry's own part of the text, where the nearest occurrence is in the line's
  own words, and how much of the text each line contains. It states a conclusion only where the
  value's line is the line the longest run stops on.

An entry with no declaring site, or with fewer than two places, is a failure. The summary prints the
registry's own shape: entries, declaring sites, mentions, and mentions with a required count. No
test asserts those numbers; the suite only checks that they count different things.

## `bindcheck.py`

Every compose bind mount must resolve outside the repo, onto a path git tracks, or onto a path git
ignores (ADR-0063 decisions 2 to 4). The rule is deliberately not "every default must be
gitignored", which would be false of `./docker/postgres/init.sql`. Git answers both questions with
`ls-files` and `check-ignore`, the latter asked with a trailing slash because compose creates a
directory and a directory-only pattern does not match a bare path.

A relative source is resolved against both project directories compose can pick, the repo root and
the compose file's own directory, and both results are asked about, which is why `.gitignore`
contains `docker/docker/`. Compose files come from `composefiles.py`, shared with the other two
compose checks. Exit 1 prints the files the reader refused first, then the uncovered paths, then one
summary per kind of problem.

## `defaultcheck.py`

One variable written in several compose files must have one default in all of them (ADR-0063
decisions 5 to 9). The check reads every substitution under `--root`, groups them by variable name
across files, and reports a group that disagrees.

The rule is not that every default is written identically. The tree has one deliberate difference:
`${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}` in an environment block against
`${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g` in two container limits, because docker parses `8.0g` as a
size and refuses it. Defaults are therefore compared as values through the same
`values.whole_spelling` that `crosscheck.py` uses, so `8.0` equals `8` and `8.5` does not. The
operator is part of the comparison: `${V:-x}` and `${V-x}` disagree about a variable set to empty,
and a variable written once is never compared. Exit 1 prints one line per refused file, then
`NAME: detail` per disagreeing variable listing every place it appears.

## `volumecheck.py`

Every volume an image declares must be covered by a mount or a tmpfs in each compose service that
runs it (ADR-0067). A `VOLUME` in an image takes effect whether or not a compose file asked for it:
a container with nothing at that path gets an anonymous volume, which `docker compose down` leaves
on the host unless it was given `--volumes`.

What an image declares is recorded in `imagevolumes.py` rather than read, because `just check` runs
on a clean dev box and in CI with no docker daemon. `--rederive`, which `just image-volumes` runs,
pulls every image it did not build, asks a real docker what each declares, and reports every row
that has changed in either direction. The pull is what makes it a fresh measurement: most of these
references are moving tags, and a local cache read would confirm a month-old image.

The cover may be a bind, a named volume or a tmpfs, and it must sit at exactly the declared path.
The rule is per compose file rather than per merged stack, because `just up` runs the base file
alone. Two further rules cover the three images this repo builds: every path one of its Dockerfiles
declares must appear in that image's row, and so must every path declared by the image its last
stage is built on, including the `ONBUILD VOLUME` triggers that base would fire. The three together
are a minimum for a built image rather than all of what it declares. A build-only service's image
name is computed as `{project}-{service}`, the project read from the file's own `name:` and
otherwise from the single bare-stemmed base file.

## `stubcheck.py`

Every comment in the body of `proto/body.proto` must still appear as a doc comment in the committed
stub `body/crates/rpc/src/_generated/cortex.seam.v1.rs`, in as many copies as the stub has
(ADR-0003 decisions 7 and 8). Both trees commit their generated stubs and regenerate them by hand
with `just proto`, so a proto edit followed by no regeneration would otherwise leave the stub
stating the old thing with every check passing.

Tonic writes each service into a client module and a server module and documents both from the one
declaration, so a service comment appears in the stub twice and each copy is required. The
comparison is over normalized text: `protocomments.py` undoes the three things prost does to a
comment, escaping `[` and `]`, rewriting a setext heading as an ATX one, and collapsing a rule line.
It runs one direction only, because the stub also contains comments tonic wrote about its own types,
and it compares text rather than generating code, which is what lets it run inside `just check`.

## `samplecheck.py`

Every log line a runbook prints back to an operator must match the call site that writes it
(ADR-0045). Four things agree per sample: the level against the method the call uses (`exception`
prints `ERROR`), the logger name against the module that declares it, the message against one a call
there writes, and the field names against exactly the keys that call attaches, in the order the
formatter prints them. Field order is name order, so one comparison covers membership and order.

Values are deliberately not compared: a sample's values are placeholders as often as readings.
Samples are found rather than registered, by reading every fenced line in `docs/runbooks/` shaped
like a rendered one, so a new sample is covered the day it is written. Only runbooks are read,
because an ADR's transcript records one run on one day and comparing it with today's code would
make the past something to edit. A call whose field list the source cannot determine, five of them
today, is compared instead against a whole rendered line its own package suite asserts
(`assertedlines.py`); the level is still compared against the call.

## `rostercheck.py`

Every list a document keeps for a set the tree really has must name exactly that set (ADR-0044).
The lists are registered in `rosters.py`: the ignored tests in the body's live suite, the modules
in `scripts/` and the two halves the contract sorts them into, the packages and crates the repo map
describes, and the tuples the constant registry is joined from.

Only the names are compared. The sentence beside each name is free, at any length and in any order,
which is why the list is written by hand. Counts are not compared, because a number beside a list
stops matching before the list does. Where a list begins and ends is data: two phrases the document
already contains, each exactly once, so several lists can share one page and one sentence can close
one and open the next. Names are read in three forms: as bullets whose name is the bullet's first
code span, as every code span matching the list's own pattern, or bare, as every whole word matching
it, which reaches a repo map written inside a fenced block. A name the sibling list owns is a
reference rather than an entry, which lets one paragraph hold two lists.

## `flagcheck.py`

Every subagent server this repo starts must use the flags its tier requires (ADR-0043). The rule is
one and the readers are two: the tier is started as a compose service and as the model host's own
hosted tier, so `subagentflags.REQUIREMENTS` runs over the union of `subagentservers.py` and
`hostedtiers.py`. A flag added to the rule reaches both placements at once.

Four requirements today: the reasoning-off pair, counted as one requirement because two flags that
must travel together are one claim; the tool-capable chat template, since a server without `--jinja`
comes up healthy with no tools at all; the host-RAM prompt cache turned off; and the thread count,
asked only of a server started with `-ngl 0`. A flag with a value is checked at every occurrence
rather than the first, because llama.cpp takes the last one. A second rule requires every model file
the tree mentions to be written under a `CORTEX_MODEL_FILE_` variable, which is what makes a server
classifiable; its domain is every artifact `artifactnames.py` finds structurally.

## `settingscheck.py`

Every setting a brain module reads must appear in the environment of the compose service that runs
it (ADR-0063 decisions 10 to 13). A variable no compose file mentions never enters the container,
whatever the host sets, and the module then runs its default with nothing reported. On 2026-09-17,
45 of the brain's 89 fields were in that state.

Both sets are computed. A service is checked when its argv runs `python -m <module>` and
`brain/packages/*/src/<module>` exists, the argv being its compose command or, for a service that
writes none, the last exec-form `CMD` of the Dockerfile it builds; that finds `brain`, `mcp-email`
and `model-host` without listing any of them. A service's keys are the union of its environment keys
across every compose file, and a bare pass-through key counts. `EXEMPT` lists the fields left out on
purpose with a reason each, and an exemption fails once a compose file adds its field or no module
reads it, so a renamed field cannot leave a stale entry behind.

## `backlogcheck.py`

Each backlog index must match the task files it describes (ADR-0039). Without `--write` it checks,
which is what `just check-backlog` runs; with `--write` it regenerates each index, which is what
`just backlog` runs. The index cannot be edited into disagreement with the tasks, because the only
supported way to change it is to change a task file and regenerate.

Five things fail it: a task file outside the layout (a name that is not `NNN-slug.md`, a missing,
duplicated or unknown field, a status outside the grammar, a title restating its own status, a
number already used, a waiting state with no trigger, or a `Verified` line that is not a date or
sits on a task that has closed or is ongoing); a relative link in a task file or an index that does
not resolve; a `#fragment` aimed at a heading its target does not offer, checked over every markdown
file in the repo; an index whose generated block is stale, missing or hand-edited; and a `tasks/`
directory holding anything that is not a task file. An index is judged on the freshly rendered text
rather than on the committed file, so a stale index stays one problem instead of a hundred.
