# scripts/ (`repo-gates`)

**Purpose.** The repo's own tooling, in the tree neither shipped artifact contains. Fourteen
gates: the cross-tree line cap, the punctuating-dash ban, the cross-language constant check, the
compose bind-mount check, the compose defaults check, the image-volume check, the seam-stub
comment check, the documented-log-sample check, the document-roster check, the subagent-server
flag check, the backlog gate, the Rust coverage threshold, the CI path classifier and the
commit-message style hook. Four more modules gate nothing and report a measurement, added from
2026-08-09: the interval a live measurement reports, the width its widest logged field renders at,
the two rates an envelope measurement's control arm is published against a floor on, and the
rendered prompt a tier's constrained verdict is predicted by.

Not all of them are gates. What every module here shares is being pure Python that belongs to
neither the brain nor the body, gated exactly like both. A standalone uv project rather than a
brain workspace member (ADR-0002).

**Public contract**. Eighteen modules have a command line. `just` recipes invoke `linecap.py`,
`dashcheck.py`, `crosscheck.py`, `bindcheck.py`, `defaultcheck.py`, `volumecheck.py`,
`stubcheck.py`, `samplecheck.py`, `rostercheck.py`, `flagcheck.py`, `backlogcheck.py` and
`coverage_gate.py`; the CI workflow invokes `ci_paths.py`; the commit-msg pre-commit stage invokes
`commitlint.py`; and the four measurement reporters run from their own recipes, `contrast.py` from
`just turn-cost`, `trailwidth.py` from `just recall-width`, `envelopefloor.py` from
`just envelope-floor` and `switchtail.py` from `just switch-tail`. Each also exposes a pure,
unit-tested core function.

**The rest have no CLI of their own**, forty nine modules, most split out under the line cap and
each named for what it holds. Grouped by the gate that reads them:

- `crosscheck.py` reads `couplings.py` for the vocabulary a registry entry is written with,
  `registry.py` for the names of the parts that registry is joined from, `values.py` for what a
  value reduces to and the form a mention writes it in, `readings.py` for how a set of those
  values must stand, and `needles.py` for how a rendered needle is searched for and what a file
  missing one is told. The parts themselves are `seamcouplings.py`, `endpointcouplings.py`,
  `shippedcouplings.py`, `boundscouplings.py`, `subagentcouplings.py`, `modelhostcouplings.py`,
  `emailcouplings.py`, `fixturecouplings.py`, `capturecouplings.py`, `overlaycouplings.py`,
  `logcouplings.py` and `trailcouplings.py`.
- `bindcheck.py` reads `composemounts.py` for the mounts a compose file declares.
- `defaultcheck.py` reads `composedefaults.py` for shell substitutions.
- `volumecheck.py` reads `composeservices.py` for what each service runs, covers and is built
  from, with `composetargets.py` split out of it for the container path one mount entry names;
  `imagevolumes.py` for the recorded answer, in the two dimensions a row has; and
  `dockerfilevolumes.py` for what a Dockerfile here declares against the row for the image built
  from it, with `dockerfilebases.py` answering the other half of that row, the image the file's
  last stage stands on. `imagedrift.py` asks a real docker for both and reports every row that has
  moved, which `just image-volumes` runs.
- `stubcheck.py` reads `protocomments.py` for what a proto comment is and how it normalizes into
  the Rust stub's form.
- `samplecheck.py` reads `logsamples.py` for what a documented log line claims to print,
  `logcalls.py` for what the call writing it really attaches, with `logfields.py` split off it
  for the field list read off the call or off the binding above it, and `loggernames.py` for
  which module owns the logger that line is written under.
- `rostercheck.py` reads `rosters.py` for every roster this repo has written down,
  `rosternames.py` for what a page's roster names, and `rostermembers.py` for the set it
  describes. `scanrecipes.py` answers the one such set that is no listing at all, which scans the
  single gate and CI both run.
- `flagcheck.py` reads `subagentservers.py` for which servers a composed stack starts as
  subagents and `hostedtiers.py` for the tier the model host starts itself, taken off the
  sidecar's own declaration with `moduleconstants.py` answering what a Python module's top level
  binds. `composestarts.py` supplies what a service is started with and what environment it is
  given, the two keys the volume gate's reader steps over. Both sets rest on `artifactnames.py`,
  every model artifact this tree names and the variable each is named under.
- `backlogcheck.py` reads `backlog.py` for the task-file grammar, `backlogindex.py` for the index
  renderer, `backloganchors.py` for the anchors a document offers with every pointer in the repo
  aimed at one, and `headingshapes.py` for what a heading may look like for that last question to
  have an answer.
- `switchtail.py` reads `switchsamples.py`, the format one run of the thinking-switch probe
  writes.
- `envelopefloor.py` reads `envelopesamples.py`, the format one arm of the envelope harness
  writes, and `envelopejudges.py`, the judge declared for each subtask shape and the three
  readings a delivered rate is taken under.

Three are shared rather than owned. `composefiles.py` is which files the four compose gates walk,
answered once so they cannot drift apart. `gitenv.py` is the environment every git call in this
tree runs with, held in one place because a caller that omits it reads the wrong repository
without reporting an error. `skippeddirs.py` is the directory components no walk here enters,
held in one place for the same reason.

- `linecap.py [--root DIR] [--max-lines N]` implements AGENTS.md gate 1. Scans
  `*.py`/`*.rs`/`*.ts`/`*.tsx` under `--root` (default `.`), all three gated toolchains
  since the ADR-0011 line-cap addendum, counting ALL lines (code, comments, blanks; cap
  default 300). Stylesheets, markup and `proto/body.proto` are outside the cap by that same
  addendum. Skips `skippeddirs.SKIPPED_DIRS`, the ten directory components no walk in this
  tree enters, plus two of its own that no other walk skips, `tests` and `_generated`
  (the generated-code marker), and test-named files (`test_*.py`, `*_test.py`,
  `conftest.py`, `*_test.rs`, `*.test.ts`, `*.test.tsx`, `test-setup.ts`, the last three
  being what `body/app/vite.config.ts` collects and sets up). `*.d.ts` is NOT exempt.
  Directory symlinks are not traversed (deliberate: no
  cycles, no escapes outside the root); a candidate that is not a regular file after
  following symlinks (e.g. a dangling editor-lockfile symlink) is skipped.
  Exit 0 with a summary line **stating what the walk measured**, files and lines counted after
  every exclusion, so a verdict that would be equally true of a tree the scan never entered says
  which tree it is over; exit 1 printing `path: N lines (cap M)` per violation;
  exit 2 if `--root` is not a directory, a source file cannot be read, or the walk measured
  **no** file at all (`MIN_FILES`), a scan that read nothing being one that cannot fail.
- `dashcheck.py [--root DIR]` implements the no-dash-as-punctuation rule (ADR-0026).
  Scans EVERY text file under `--root` (default `.`), not just `*.py`/`*.rs`, because the
  rule covers docs and comments alike. **Its collection is the working tree minus what git
  ignores** (ADR-0026 dash-ban-collection addendum): the tree rather than `git ls-files`, so a
  file staged but not committed and a file an agent wrote a minute ago are both read, that being
  the prose this repo is about to own; minus what git ignores, so generated schemas, a coverage
  export and a live measurement's JSON blocks are not reds whose remedy is deleting a file. Git is
  asked once for the paths it ignores and a wholly ignored directory is pruned rather than
  descended, which is what keeps an unignored walk out of the GGUFs under a bind target. `--root`
  must therefore name a git working tree. Flags U+2014 EM DASH and U+2013 EN DASH anywhere,
  spaced or not, since a range takes a plain ASCII hyphen. Deliberately silent on U+2212
  MINUS SIGN (arithmetic), and on ASCII `--` (the repo's inline-reason idiom, which the gate-2
  escape-hatch rule effectively requires; commit messages are stricter and `commitlint.py`
  bans it there). Skips `skippeddirs.SKIPPED_DIRS`, which is what `linecap.py` skips minus
  `tests` and `_generated`, since prose in a test or a generated stub is still prose; the two
  lists cannot drift, the cap composing its own from this one. That list is partly redundant
  with the ignore answer and stays anyway, on two names out of ten: `.git`, which git does not
  call ignored, and `coverage`, which the repo ignores only under `body/app/`. Binary files are
  detected and skipped. A line carrying `dashcheck: allow` plus a reason is exempt, for a
  dash that means rather than punctuates. Exit 0 with a summary **stating the text it read**,
  files and lines with the binaries and the ignored in neither; exit 1 printing
  `path:line: kind: text` per violation; exit 2 if `--root` is not a directory, git cannot say
  what it ignores there (fail closed, as `bindcheck.py` does about the same dependency, since the
  collection would otherwise be undefined), a file
  cannot be read, or no text file was read at all (`MIN_FILES`, the same floor `linecap.py`
  carries and the one `composefiles.py` has always given the two compose gates). That floor now
  has a second road to it, a root git ignores entirely, which is the same empty collection
  arriving a different way.
- `crosscheck.py [--root DIR]` ties the values this repo spells in more than one place, because
  both sides of a seam must hold the same one and neither toolchain can import the other's
  (ADR-0029 cross-language-constant addendum and its 2026-08-08 widening). The scan is all of the
  logic; the `*couplings.py` files are all of the data,
  one entry per value: a
  label, the reason its places must agree (printed with any failure), its `Site`s, an optional
  `relation`, and optional `mentions`. The registry is written in several data files and read as
  one. `registry.py` is the only module that names them, so a new part is a data file plus one line
  there and the scan never learns the registry has parts; `crosscheck.CONSTANTS` is
  `SEAM_COUPLINGS`, then `ENDPOINT_COUPLINGS`, `SHIPPED_COUPLINGS`, `CAPTURE_COUPLINGS`,
  `BOUNDS_COUPLINGS`, `SUBAGENT_COUPLINGS`,
  `MODELHOST_COUPLINGS`, `EMAIL_COUPLINGS`, `FIXTURE_COUPLINGS`, `OVERLAY_COUPLINGS`, then
  `LOG_COUPLINGS` and `TRAIL_COUPLINGS`. Each part is named for its subject: couplings whose
  far side is another tree's code across the language boundary; the address and port each side
  answers on, with every file that dials or states one; the brain container's own shipped
  defaults, restated by a compose default, a runbook row or a module contract; one capture's
  own edge, byte budget and deadlines, which are that same kind narrowed to a single request;
  the four bounds one delegated run stands between, each held to the runbook and the module
  contract that quote it and to no stack at all, since nothing under `docker/` ships one of
  them; the subagent tier's
  admission budgets with the cgroup limits that are their hard twins,
  and the reasoning-off flag pair every server in that tier starts with, held as one
  needle whose value is the budget's count and whose shape is the two flag names around it; the model-host tier settings
  and the
  override that ships them; the email sidecar's three safety answers and the override that spells
  each again, with the four texts it composes without reading a message, the `_meta` key it
  declares a sender under, the kind word that declaration carries and the two field names it is
  written under, each held to the brain package that restates or reads it; a stack
  built to be measured against and the suite that measures it, the one subject
  the repo does not ship; the overlay's TypeScript against its own stylesheet; the brain's log
  vocabulary, the one name each work identity is written under, against every line that spells it
  and every runbook that tells an operator to grep it, the first of the two parts whose subject
  is a name a line is written with rather than a value one carries (ADR-0009 one-vocabulary
  addendum), whose turn entry also holds the one qualified spelling in the brain, the second
  turn named on a single line, through a template that renders the qualifier in front of the
  same declared value, so a rename of the family cannot leave the qualified name behind
  (sixth-name addendum); and the second such part, the words one line of either per-line trail is
  found by, which are one line's where the log vocabulary is one word's
  across the brain: the recall trail's logger, held to the two runbooks and the module
  contract that restate it (ADR-0038 named-logger addendum), and the message and the field name
  `trailwidth.py` spells to find and cut the recall trail's widest value out of a captured line.
  Those two are the one place in the registry where the DECLARING side gates nothing: a reader
  run by hand on a GPU is exactly the far side that can move without failing a suite, which is
  the argument the fixture part already makes for a subject nothing ships (ADR-0038 tied-needle
  addendum). The tool audit's logger is the fourth entry there and the same shape as the first,
  held to the tools runbook, the local-dev runbook, the docstring that argues from it that the
  shipped level is not a knob, and that module's suite, which writes a line under the name to
  prove the argument and would go on proving it about an abandoned logger (ADR-0009 audit-logger
  addendum). Its message is the fifth, held to the runbook sentence that tells a reader what to
  look for and to that same suite, which spells the word twice and so renames with itself; the
  sample gate is no substitute, that sink's fields being built by condition, so no runbook may
  print one of its lines as a rendered sample at all (ADR-0009 audit-message addendum). The
  suite's asserted line is where the two entries meet, each rendering its own half of
  `LEVEL:logger:message` rather than spelling the other's as fixed text. Three of those values are
  declared in a sink and handed to their call as an identifier, which carries no string a scan can
  read, so what holds each to the call handed it is named rather than left to be noticed: the
  audit message names that sink's package suite, which asserts four whole rendered lines and is
  the only thing holding this trail's message to the call handed it, and it was already holding it
  without saying so, which is what registering it buys (ADR-0009 declared-name addendum). The two
  loggers name nothing, because what holds them names no logger: the sixth entry is the identifier
  `_LOGGER_NAME` itself, declared by the gate suite's guard on the self-named sinks, which reads
  which sinks those are off the tree and asks each of those modules for that one binding, and
  spent by both sinks and by both module contracts explaining why a sink is spelled that way. That
  is the naming a derived set is read by rather than a list of the sinks in it, so a third one is
  held the day it is written, and what a needle catches is the guard going away or a sink renaming
  its declaration alone (ADR-0009 derived-sink addendum). Some arrived as
  splits under the cap and some as subjects added beside them, which is the one-line claim being
  paid from both directions rather than argued.
  `couplings.py` is the vocabulary every part is written in, left behind when each moved out
  under the cap. Nothing in the scan depends on which file an entry sits in, and no number counts
  the parts: the list in `registry.py`'s docstring is the whole answer to what the registry is
  written in, and the suite holds it to the directory beside it and to the order the tuple reads
  them in, so it cannot fall short of the files on disk (ADR-0029 registry-parts addendum). Every
  entry lives in exactly one part and `CONSTANTS` holds nothing of its own, which the suite holds
  too (ADR-0029 registry-equality addendum).
  `values.py` and
  `readings.py` are the pieces neither the scan nor the data is: the first reduces a right-hand
  side to a comparable value and says how a mention may spell it, the second says whether a
  constant's readings hold together, so the scan finds declarations and those two judge them.
  `needles.py` is the third such piece, on the mention's side rather than the site's: it holds how
  a rendered needle is bounded and looked for, and what a file that does not carry one is told
  about which of the needle's literals stopped matching.
  **A `Site` declares the value** (a repo-relative path plus the identifier declared in it) and is
  read and compared. The identifier is a name a file **declares**, never a name a module exports,
  so a module-private one is registrable and `_UNRESTRICTED_REASONING` is registered under its
  underscore: this scan reads text and imports nothing, and widening an API to suit a reader would
  be the gate editing the contract it watches. What that costs is a rename nobody tells the
  registry about, and an unreadable place is a fault here rather than a skip, so the rename is
  reported. **Nor does a site have to sit in a tree `just check` compiles or runs.** The scan reads
  text and imports nothing, so the file it reads need only exist: `DEFAULT_BODY_PORT` is declared
  in the ungated Tauri shell, whose clippy lives in CI's `check-shell` alone (ADR-0023 port
  addendum), and the probe fixture's names, the account it logs in as among them, are declared in
  an `integration`-marked test module no CI run executes (ADR-0029 fixture addendum). Both are held on every `just check`,
  which is more often than either is built or run, and that is the argument for reading them here
  rather than the objection to it. **A `Mention` spends it without declaring it** (a path plus a template
  carrying `{value}`): the scan renders the agreed value into the template and requires the result
  to appear in the file **as a token of its own**, `bounded()` guarding whichever of the needle's
  two edges is itself a word character, and guarding a digit edge twice. That is not circular, since the template carries the shape
  and the site carries the value, and it is what lets the gate reach a key spelled inside a shell
  string, a custom property a stylesheet reads back with `var(...)`, and a bare literal a component
  compares against, with no promotion to a named constant first.
  **A mention may render a NAME instead of, or beside, the value.** Where the far side names the
  value rather than restating it, a rendered value reaches the declaration and never the spend:
  `overlay.css` writes `--roll: 300ms` once and pays it as `var(--roll)` twice, and only the first
  of those carries a number. So `Mention.name` is the name that far side spends it under and
  `{name}` renders it, which makes the pair two mentions of one entry, `{name}: {value}ms;` over
  the declaration and `var({name})` over the spends. A mention carries a name exactly when its
  template renders one (either half alone is dead data and a fault), and the registry rejects a
  name pinned as a spend that no site of the same entry declares and no mention of it renders a
  value under, which would hold the name while quietly dropping the value. A site pays the name it
  declares, reading the declaration being reading the value under that name, so a Python call
  handing a registered binding by name is a spend of that site (ADR-0009 held-call addendum). Two
  properties live in this shape, `--roll` and `--ease`, being the two the overlay's TypeScript
  declares the value of rather than the name, and one message, the tool audit's, whose entry
  carries `_logger.info({name},` over the sink that declares the binding.
  **Bounded, and written to cover the whole of what it pins.** Bare containment passed on two real
  violations: a value that is a prefix of the one written down (`5005` inside `50051`), which the
  bound now refuses, and a published `host:container` port pair whose host half alone carried the
  needle, which is a template question rather than a matcher one, so the compose publish is
  registered as `"127.0.0.1:{value}:{value}"` and the healthcheck dial beside it as its own
  mention.
  **A point flanked by digits is inside a number** (ADR-0029 decimal-edge addendum), which is the
  one continuation a word edge cannot see: a point is not a word character, so `10` was a token of
  its own inside both `10.09` and `0.10`. A digit edge therefore takes a second guard beside the
  word one, reading the FAR side of the point rather than the point itself, so `2048.` ending a
  sentence stays found and `2048.5` does not. An edge that is a word but not a digit takes no such
  guard, `grpc.` before a needle opening with a letter being attribute access and a key numbered in
  the middle (`tiers.2.auto`) being neither half of a decimal. The verdict on the live tree does
  not move, every needle in it carrying a name, a unit or a table wall; what moves is the value
  reading below, which searches the bare number and so sits next to every decimal in the file.
  **An unfound needle says whose literal stopped matching** (ADR-0023 misattributed-fault
  addendum). A needle is a value plus shape and the shape is other people's text, so moving a
  neighbour's value out of a template fails the entry beside it: the compose publish's host-side
  interface and the body app contract's `CORTEX_BRAIN_ADDR` default each reported *the brain's
  seam port*, which neither of them spells. `needles.py` now answers the fault with two readings.
  The first is whether the file **still spells this constant's own value** as a token of its own,
  which is the evidence that what moved is shape and that the entry named is probably not the entry
  to change; a mention rendering only a name spells no value at all and is told so instead. **A
  yes says where it read one** (ADR-0029 still-spelled addendum): how many places spell the value,
  and of those the one nearest where the run below stops, named by line number and read back with
  the line's own words, windowed to `needles.QUOTED_WIDTH` because the widest line this gate reads
  is a runbook table row. A maybe a reader has to grep is the work the reading exists to save, and
  the case that opened it was a `~11 GB` in a paragraph about VRAM answering yes for a stop grace
  retuned to `11.0`. A needle opening with its own value has no shape in front of it to be nearer
  to and degenerates to the first occurrence; a file carrying no part of the needle names the first
  for want of a run. The
  second is the **longest opening run of the needle the file carries**, which pinpoints the
  divergence where the shape is unique to the needle. That run is measured over the whole file
  rather than one line, because a mention names a file, so a prefix satisfied on another line makes
  it longer than the divergence a reader is looking at: the compose interface moving still leaves
  `"127.0.0.1:` carried, by the redis publish below it. It is worded as the most of the needle the
  file carries anywhere, and it is the second half of the message for that reason. **That run
  names its line too** (ADR-0029 run-line addendum), and how many places carry it, in the value
  reading's own three shapes, because the distance between the two lines is the evidence a reader
  weighs: a value on the line the run stops on is the strong form of "what moved is shape" and one
  seventy lines away is the weak form. Which occurrence each names is one rule rather than two.
  `needles.nearest` picks the closest **pair**, so the value is the spelling nearest where the run
  stops and the run is the stop nearest that spelling, and where one of them is missing both fall
  back to the first occurrence and the message says which rule it used. The distance itself is
  deliberately not computed: two line numbers are the comparison, and a gap in lines would
  sometimes disagree with a pair chosen by distance in characters.
  **Only the strong form draws a verdict** (ADR-0029 word-valued-verdict addendum). `needles.MET`
  is the sentence naming the shape as the likely mover and the entry named as probably not the one
  to change; `needles.APART` reports both readings and names neither, and `needles.verdict` picks
  between them on whether the value's line is the line the run stops on. The weak form used to
  draw the strong form's conclusion, which is wrong wherever the value is an ordinary word: with
  `SourceKind.SENDER`'s value renamed alone the gate found `sender` in seven places of the core's
  own docstrings and said the shape had moved, and with the declared-source value field re-spelled
  `from` it found that word thirteen times in the tools contract's prose and said the same. Both
  readings still print, so a reader who wants the hunt has the line numbers; what is withheld is
  the sentence sending them to a neighbouring constant.
  **Re-spelled where the far side's syntax cannot take the value as written** (ADR-0029 spelling
  addendum). `Mention.spelling` is `Spelling.WRITTEN` by default, which is the site's own text;
  `Spelling.WHOLE` renders the same number with no fractional part, for a syntax that carries none
  (docker parses `mem_limit: "8g"` as a size and refuses `8.0g`, so the subagent memory budget is
  spelled `8.0` in the environment block and `8` in the two container limits of one compose file);
  `Spelling.LOWERED` folds a boolean's word to the case the other language writes it in, for the
  compose default that spells `false` where the field it restates declares `False`, and refuses
  anything that is not a boolean (ADR-0029 boolean addendum).
  The second spelling is DERIVED by `values.spell` and never typed into the registry, so one number
  is still written down once, and a value it would have to change to fit is refused: a budget at
  `8.5` fails the scan naming the far side that cannot spell it rather than quietly capping a
  container half a gigabyte under what the scheduler admits. A LOSSY re-spelling is blind to a site
  that drops its point (`8` and `8.0` are one whole number and one whole spelling), which is the
  drift the textual reduction exists to catch, so `values.spelling_fault` refuses an entry whose
  mentions all spell lossily: a second site, or a mention rendering the value faithfully, must
  stand beside them. `Spelling.lossy` is which kind a spelling is and is the question that rule
  turns on: a whole spelling is lossy and a case fold is not, `False` and `True` lowering to two
  different words, so an entry whose only mention lowers a boolean holds the drift by itself.
  **Counted where the occurrences are one set.** A mention is a presence check unless it carries
  `occurrences`, so a file spending the value twice and losing one of them passes by default,
  which is what a half applied rename looks like. `occurrences` pins an EXACT number of bounded
  matches rather than a floor, because a floor cannot notice the far side has grown past it and so
  widens itself by however much the tree drifted; a count below 1 is refused, zero being a mention
  asking the value to be absent. It is opt in, and the survey that set it is in the ADR. How many
  mentions carry a count is a number this doc no longer states, the scan's own success line
  answering it; what is worth writing down is which ones and why. `Message.tsx` at 2 (the
  `className` and the
  `aria-label` of one chip), `docker-compose.subagents.yml`'s `mem_limit` pair at 2 (memswap equal
  to memory is what disables the container's swap, so one moving without the other re-enables it in
  silence) and its `cpus` pair at 2 (the budget passed to the scheduler and the cgroup cap on the
  container serving what it admits), each logical model id in `docker-compose.gpu.yml` at 2 (passed
  to the sidecar and probed again in the healthcheck beside it), `overlay.css`'s
  `:not([{value}="0"])` at 2 (the two section share
  caps, whose handover is symmetric or nothing), `overlay.css`'s `var(--roll)` at 2 (the two
  rules that must land WITH a roll, which is the set the entry's own reason names),
  `probe-mailboxes.sh`'s guarded mailbox at 2 (the directory and the ACL file inside it, since a
  rename that moved only the first leaves the ACL somewhere dovecot never reads and the mailbox
  opens like any other), and the probe account's mail home in that same script at 2 (the tree is
  built under it and chowned by it, and `set -eu` stops the script when one of the two moves
  alone, which is loud and arrives only when somebody next measures; the root above that home is
  the environment variable the compose file hands in, spelled once there and read by the script
  and the conf, so the needle renders the account under the variable and there is no second
  spelling of the path for a row to hold, ADR-0022 one-mail-root addendum), and the ones the
  prose sorts
  added, every one of them a file stating one shipped value twice where losing one leaves it
  naming two different answers at once: the volume runbook's endpoint pair and its export pair,
  the body app contract's two stated binds, the GPU runbook's two recipe lines, the vision
  runbook's three token-budget claims, and, for the brain's own port, the body RPC contract's two
  stated endpoints and the Rust live suite's stated default beside the fallback it uses, and the
  GPU runbook's two reasoning-budget Default cells, one per tier, since a file naming one tier
  unbounded and the other bounded states a split the config does not have. Those are all the shape
  a presence check reads as green while half the file is wrong, since each file spells the number
  in two places for two different readers. Meanwhile the bare
  `[{value}` mention stays a presence check because its three rules are the sum of two unrelated
  features and `var(--ease)` stays one because 52 transitions across unrelated features ride that
  curve. Every mention that occurs once is left unpinned, a count of one saying nothing a presence
  check does not.
  **`Relation`** is `EQUAL` by default; `ORDERED` holds an entry's sites to non-decreasing order
  in registry order, for a bound that must sit under another rather than match it. An ordering
  compares integers only, a signed one included (a string under one is a fault, and so is a
  decimal, which is text here and would sort `10.0` under `9.0`, and so is a boolean, an answer
  with two values having no order at all), and it may carry no mentions, there being
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
  so `6291456` and `6 * 1024 * 1024` tie; the six forms that reduce are a product of integer
  literals, which may open with a minus (the sign is the expression's and never a factor's, and a
  leading plus is refused, `str(1)` rendering a needle `+1` does not spell), a plain double-quoted
  string, a parenthesized run of double-quoted literals across several lines, which reduces to
  the one string Python joins them into and is the one multi-line shape the Python declaration
  syntax captures (how this repo writes a sentence too long for one line, held first for the
  email sidecar's own texts, ADR-0029 run addendum), a one-line `frozenset` of those strings,
  which is how this repo spells an allow-list and is what a membership is decided against (a set
  literal is mutable, and a multi-line collection never reaches the reducer, every other
  declaration being captured one line at a time), a decimal literal, and a boolean.
  **A decimal reduces to its digits rather than to a number** (ADR-0029 decimal addendum), which is
  the one place the reducer stops short of arithmetic: `5` and `5.0` are one number and two
  spellings, and the spelling is what a mention needs, a needle rendered as `5` finding nothing in
  `${CORTEX_BODY_CALL_TIMEOUT_S:-5.0}`. So a decimal becomes a `values.Digits`, its own type so it
  cannot tie to a string literal spelling the same characters, and it compares as text: a site that
  drops its point stops agreeing, where a float would have kept agreeing while every place spending
  it went unfound. Digits, one point, digits, with `_` grouping either run; a leading or trailing
  point, a sign, an exponent and a language's own type suffix are refused with everything else the
  reducer will not guess at.
  **A boolean reduces to its word rather than to a truth value** (ADR-0029 boolean addendum), for
  that same reason and one Python adds: `False` IS an `int` that equals `0`, so a bare `bool` would
  tie to a site declaring zero and would sort under an ordering that has no business over an answer
  with two values. So a boolean becomes a `values.Truth`, and the two words a SITE may write are
  Python's own `True` and `False`, that being the only language a registered boolean is declared
  in; a second language's casing at a site would be two texts for one answer, and a far side that
  writes one is reached by `Spelling.LOWERED` instead. `DECLARATIONS` holds one declaration syntax
  per language (`.py`, `.rs`, `.ts`), matching module-level and item-level constants only: the
  Python and TypeScript forms are anchored at column 0, so an indented `const` is a local and not
  a second declaration of the module's constant. A mention needs no declaration syntax, so its
  file may be any text at all (`.css`, `.yml`, `.tsx`).
  **Fails closed by design**, because a scan that cannot find its constants would agree with
  itself forever: a missing file, an unreadable or non-UTF-8 one, an unknown suffix, a name
  that is absent, one declared twice, a value it cannot reduce, a mention whose rendered needle is
  absent or found a different number of times than it pins or whose template renders neither
  `{value}` nor `{name}` or renders a name it does not carry or carries one it renders nowhere
  or pins a count below 1, a name pinned as a spend that no site declares and no mention pays a
  value under, and a registry entry naming no declaring site or
  fewer than `MIN_PLACES` (2) places are each a fault, never a skip. Exit 0 with a summary; exit 1
  printing `label: detail` per fault; exit 2 if `--root` is not a directory. **The summary states
  the registry's own shape**, `registry.shape` counting entries, declaring sites, mentions and
  mentions pinned to a count over the same tuple the scan walks. That is the collection every
  mutation table in this repo opens by naming, and it is a reading rather than a gate: see the
  census bullet below for why nothing asserts it. It counts places and **not parts**, declined
  rather than overlooked (ADR-0029 registry-parts addendum): nothing the scan does depends on how
  many files the data sits in, a part that never reached the tuple is caught by the suite reading
  the directory, and a whole part gone missing already moves the entry count.
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
  project directory is `docker/`. Compose files are found by `composefiles.py`, shared with
  `defaultcheck.py`, so a new override is covered wherever it is added and the two compose gates
  cannot come to disagree about which files exist. **Fails closed**: no compose file at all, a mount entry the
  reader refuses, a source that cannot be reduced, and a git that cannot run are each a fault,
  never a skip. Exit 0 with a summary **stating what the walk read**, compose files, the binds
  they declare, and the landings git was asked about, which is neither the binds nor twice them;
  exit 1 printing `path:line: detail` per fault; exit 2 if
  `--root` is not a directory or the scan could not run at all.
- `defaultcheck.py [--root DIR]` holds one variable spelled in several compose files to one
  default in all of them (ADR-0026 defaults addendum). It is compose-only and registry-free: it
  reads every substitution under `--root`, groups them by variable name across files, and reports
  a group that does not agree. **The rule is not that all spellings are identical.** The tree
  carries one deliberate re-spelling, `${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}` in an environment
  block against `${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g` in two container limits, because docker
  parses `8.0g` as a size and refuses it. So the defaults are compared as a **value**, through the
  same `values.whole_spelling` `crosscheck.py` renders that pair with: identical text agrees with
  nothing to reduce, and anything else must reduce and re-spell whole, so `8.0` ties to `8` and
  `8.5` does not, its fraction being lost rather than zero. **The operator is part of the answer**:
  a group's spends must fall back the same way as well as to the same value, `${V:-x}` and
  `${V-x}` disagreeing about a variable set to empty and `${V:?}` beside `${V:-x}` being one file
  demanding what another supplies, and only the operators whose argument is a value at all are
  compared, two `:?` spends wording their message differently having not drifted. A variable
  spelled once is never compared, having no sibling to disagree with. **Why it is not folded into
  `crosscheck.py`**: that scan is registry-driven and its subject is a value some tree declares
  against the places restating it, while this question has no declaration and is discovered by
  walking the files, so the fold would give one scan two entry points and make its stated subject
  false. **Fails closed**: no compose file at all, a file that cannot be read or decoded, and a
  `$` form the reader was not taught are each a fault. Exit 0 with a summary **leading on the
  variables actually compared**, over the compose files and the variables read to find them,
  since a variable spelled once is not in the collection the verdict is about; exit 1 printing
  `NAME: detail` per fault, each naming every place the variable is spelled; exit 2 if `--root`
  is not a directory or the scan could not run at all.
- `composedefaults.py` is `defaultcheck.py`'s reader and has no CLI. `read_substitutions(text)`
  returns one `Substitution(line, name, operator, argument)` per spend, in file order. It is a
  character walk rather than a YAML parse, because compose interpolates the strings a YAML parse
  has already produced, which is what lets one variable be read the same way as a whole value,
  inside a connection string and inside a command argument. Seven forms are read (`${N}`, `$N`, and
  the three operator pairs `:-`/`-`, `:+`/`+`, `:?`/`?`), the operator kept as written rather than
  folded. `$$` is compose's literal dollar and is consumed whole, so `$${V}` spends nothing. A
  whole-line comment is skipped, compose interpolating nothing in one, which leaves a default
  written there as prose and therefore `crosscheck.py`'s question; a **trailing** `#` is read like
  any other text, and that is settled rather than deferred (ADR-0026 trailing-note addendum): a
  marker can only be found by tracking quotes and block scalars across a file, which is a YAML
  parser in a dependency-free project, and the strictness it would buy off is loud and one line
  from its remedy where a mistaken marker would drop a real spend in silence. Everything else
  raises `SubstitutionReadError`: a `$` opening none of those forms, a
  brace that never closes, a nested expansion (which compose does not expand), a name that is not
  an identifier, and an operator it was not taught.
- `composefiles.py` is which files the compose gates walk and has no CLI. `compose_files(root)`
  returns every compose file under `root` by name (stem `docker-compose`/`compose`, suffix
  `.yml`/`.yaml`), skipping the vendored directory components, and raises `ComposeSearchError`
  on none, a scan whose glob matched nothing being one that reports success forever. It is one
  module rather than a copy in each gate because a second walk is a gate that learns about a new
  override while its sibling does not, in silence. The components it skips are
  `skippeddirs.SKIPPED_DIRS`, shared with every other walk here; it carried a shorter list of its
  own until that module landed, and joining changed neither compose gate's reading.
  `base_project(...)` is the same question asked one step further and lives here for the same
  reason: only the bare-stemmed file is what compose reads when handed no `-f`, and only it pins
  the project name an override inherits, so a gate keying a build-only service as
  `{project}-{service}` needs the stems this module already owns. Exactly one such file must pin a
  name; none and several both return `None`, and the caller draws a fault rather than keying a
  silently wrong row.
- `skippeddirs.py` is the directory components no walk here enters and has no CLI: ten names,
  read by all four walks (`dashcheck.py`, `linecap.py`, which composes its own list from it,
  `backloganchors.py` and `composefiles.py`). **It is deliberately not `.gitignore`**, and the
  overlap is measured rather than believed: eight of the ten are names git ignores wherever they
  appear, `.git` is never reported ignored (it is not part of the work tree), and `coverage` is
  ignored only under `body/app/`, by that tree's own file. Collapsing the list to `.git` and
  asking git for the rest would make the line cap, the anchor scan and the compose walk refuse a
  root git cannot answer about, which is `just check` refusing to run outside a git working tree;
  only the dash ban has a rule whose collection is git's answer. `test_skippeddirs.py` holds both
  claims: every walking module reads this list rather than a copy, and the eight-two partition
  against git's own answer for this repo, which fails from either side.
- `composemounts.py` is `bindcheck.py`'s mount reader and has no CLI. `read_mounts(text)` returns one
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
- `volumecheck.py [--root DIR] [--rederive]` holds every volume an image declares to a mount or a
  tmpfs in each compose service that runs it (ADR-0011 out-of-reach-evidence addendum). A `VOLUME`
  in an image is a promise docker keeps whether or not a compose file asked for it: a container
  with nothing at that path gets an **anonymous** volume, filled from the image, which the
  `docker compose down` that did not say `--volumes` leaves on the host under a generated name,
  one per start. **What an image declares is recorded rather than read**, in `imagevolumes.py`,
  because `just check` runs on a clean dev box and in CI, where there is no daemon and no image
  pulled, and one recipe is already deliberately outside the single gate for needing system
  libraries. `--rederive` is the other half and what `just image-volumes` runs: it **pulls** every image it
  did not build, asks a real docker what each declares, and reports each row that has drifted, in
  **both** directions, since a stale row and an unrecorded image are one drift arriving from
  opposite sides. The pull is what makes it a re-derivation rather than a confirmation: `docker
  image inspect` answers out of the local cache, most of these references are moving tags, and a
  cache read would confirm a month-old image under a name the registry has republished. A pull it
  cannot do is reported rather than answered from the cache; the three images this repo builds are
  asked without one, having no registry to be refreshed from. The cover may be a
  bind, a named volume or a tmpfs, and it must sit at **exactly** the declared path, a mount over
  the parent leaving docker's declaration standing. **The rule is per file rather than per
  layered stack**, because `just up` runs the base file alone, so a base service whose declared
  path were covered only by an override really would leak and a reader that merged first could not
  say so, which is also why a service naming neither an image nor a build is read as a fragment
  and asked nothing. **A second rule covers the three rows this repo builds**, where the record can
  move under the gate from inside the tree rather than from a registry: every path a Dockerfile
  here declares must appear in the row for the image built from it (`dockerfilevolumes.py`), and
  so must every path declared by the image that file's last stage stands `FROM`
  (`dockerfilebases.py`), the record carrying a row for each of those two bases and pulling it on
  every re-derivation because a built row can never be pulled at all. **A third covers what a base
  declares for its children**, the `ONBUILD VOLUME` its own `Config.Volumes` never shows and the
  next build from it makes real: every path the base row's recorded triggers name must appear in
  the built row too, read with the same `VOLUME` grammar. Between them the three sides
  are a **floor** under what a built image declares rather than the whole of it, which was measured
  rather than assumed: a declaration is inherited through `FROM`, a builder stage's reaches no
  built image, a Dockerfile cannot un-declare what it inherits, and a base's `ONBUILD VOLUME` adds
  a path to the image built from it while leaving that base's own row empty. That last one is why
  the trigger dimension is recorded and why the three built rows are recorded and not derived from
  the sides at all, and why every rule
  is one-directional: a recorded path no side declares is not merely nobody's fault, it is
  the only place a further source can appear (ADR-0011 addenda on why the built rows stay
  recorded and on what a base declares for its children). Thirteen things
  fail it: a declared path no service
  covers, an image the record
  has no row for, a base the record has no row for, a base declaring a path the built row does not
  carry, a base whose trigger would declare a path the built row does not carry, a recorded trigger
  the reader will not guess at, a row nothing here names, an image spelled through a substitution
  the record
  cannot be keyed on, a service that only builds where no base file pins the project half of its
  image name, a compose file the reader will not guess at, a Dockerfile declaring a path its row
  denies, a build stanza reaching no Dockerfile under either project directory, and a build path
  spelled through a substitution. Under all thirteen sits
  `composefiles.py`'s floor, shared with the other two compose gates, where finding no compose
  file at all is a failure rather than an empty pass. **A build-only service's image is derived**
  as `{project}-{service}`, the project read from the file's own `name:` and otherwise from the
  single bare-stemmed base file, which is why `cortex-brain` and `cortex-mcp-email` are rows and
  why `cortex` is not spelled a second time. Exit
  0 with a summary stating the coverings checked over the files, services and images read and the
  Dockerfiles the builds were followed to; exit 1
  printing `path:line: detail` per fault; exit 2 if `--root` is not a directory or the scan could
  not run.
- `imagevolumes.py` is `volumecheck.py`'s record and has no CLI of its own. `IMAGE_VOLUMES` maps
  each image reference a compose file names to a `Row`, which is what docker answered about it in
  **two dimensions**: `volumes`, the paths it declares of its own, sorted, and `onbuild`, the raw
  `Config.OnBuild` triggers it would fire into anything built `FROM` it, in docker's own order. An
  empty tuple in either is a measured answer rather than a missing one, which is what lets the gate
  tell a silence somebody measured from an image nobody has asked about; both are asked in one
  inspect, so a row cannot half-exist. The trigger dimension is recorded raw rather than as the
  paths it resolves to, since the record holds what docker said and a resolved path is a reading of
  it, made once on the machine that ran the recipe rather than by the gate everyone runs. Two of
  its rows are named by a `FROM` in this tree
  rather than by any compose file: they are the bases the three built rows stand on, recorded
  because a built row is asked without a pull and so answers from whatever the machine running the
  recipe last built, while a base row is refreshed from its registry every time. Its docstring
  carries the dates each row was measured on and why the three built rows are spelled the way
  compose tags them.
- `imagedrift.py` is the other half of that record and has no CLI. `INSPECT_FORMAT` is the
  `docker image inspect --format` string every row was measured with, printing two lines of JSON,
  one per dimension; `parse(output)` reads them back into a `Row` and raises `InspectError` on any
  shape it was not taught, which keeps the decision out of the adapter and in code the coverage
  gate reaches, and reports an unreadable answer as a row that went unchecked rather than as an
  image declaring nothing. `docker_volumes` is the only part needing a real daemon and is the
  module's one `pragma: no cover`, and it is where the pull lives; `rederive` decides everything,
  including which references are refreshed and which are local builds, and takes any inspector, so
  the comparison is tested against a fake. It compares the paths as a set and the triggers as
  written, since triggers fire in order, and reports each dimension that moved on its own line.
  `report_drift` prints that comparison and returns the exit code behind `--rederive`.
- `dockerfilevolumes.py` is the tree's own side of that record and has no CLI. `read_volumes(text)`
  returns every container path one Dockerfile declares, in both spellings docker accepts, the JSON
  array and the plain list, joined across continuation lines and matched however the instruction is
  cased. `ONBUILD VOLUME` is deliberately not one, and that refusal is a correctness requirement:
  it declares a volume in an image built *from* this one, so reading it here would make the rule
  demand a path in the row for an image that truly declares none. Where a trigger does belong is
  `onbuild_volumes(entries)`, which reads the raw `ONBUILD` a base's row carries with the same
  grammar, each entry being one whole instruction as docker wrote it down: an entry naming another
  instruction declares no volume, and a `VOLUME` it cannot read is refused rather than resolved to
  nothing. Everything else raises `DockerfileError` rather than being walked past, since a skipped
  `VOLUME` is a declared path the record would go on denying: an argument carrying a build argument
  or an environment variable, a path that is not absolute, a JSON container that is not an array of
  paths, and a `VOLUME` naming nothing. `undeclared(...)` is the rule over it and reports what no
  row carries, taking
  the Dockerfile from the compose service's `build:` rather than from a record of its own, since a
  second spelling of that mapping is the same defect one level down. It asks the base halves over
  the same read, what the base declares and what its triggers would declare, so a file is opened
  once and an unreadable one owes one fault rather than three.
  `landings(...)` resolves a
  relative context against **both** project directories compose can pick, exactly as `bindcheck.py`
  resolves a bind source, and an absolute one lands once rather than twice.
- `dockerfilebases.py` is the other side of a built row and has no CLI. `read_base(text)` returns
  the image a Dockerfile's **last** stage stands on, which is the only stage whose config survives
  a build: measured with docker on 2026-08-28, an image built from a base declaring `/probe/base`
  declares it too, while a `FROM ... AS builder` stage declaring `/probe/builder` contributed
  nothing, which is why `brain/Dockerfile`'s `uv` builder stage gets no row. A last stage naming an
  earlier one is followed back through the stage names, however either side cases them, until it
  reaches something that is not a stage; `FROM scratch` stands on nothing and returns `None` rather
  than being sent looking for a row. A `--platform` flag is dropped, changing nothing about what
  the named image declares. Everything else raises `DockerfileError`: an image spelled through a
  substitution, a file with no `FROM` at all, a `FROM` that is not an image optionally named with
  `AS`, and a stage standing on itself or on one written after it, which no build could resolve.
  `inherited(...)` is the rule, one-directional like its sibling: every path the base's row carries
  must appear in the built row, and an unrecorded base is an unasked question rather than a pass.
  It hands back that row's raw triggers with the base it found them under, for
  `dockerfilevolumes.py` to read with the `VOLUME` grammar it owns and hold to the built row the
  same way: a base declares for its children through `ONBUILD VOLUME`, which its own
  `Config.Volumes` never carries and the next build from it makes real.
  The file's own grammar lives here too, `logical(text)` joining continuation lines and dropping
  comments and refusing an `escape=` parser directive that would change what a continuation means,
  because a stage cannot be found before the lines are joined and both readers work over the same
  ones.
- `composetargets.py` is the container path one mount entry names and has no CLI. It is the half of
  `composeservices.py` that answers what `composemounts.py` deliberately does not: that reader takes
  a mount's source and drops every entry naming none, this one takes its **target**, where a named
  volume, a tmpfs and a bind cover a declared path equally well. Four spellings reach it and all
  four mean one path: the short `source:target[:mode]`, the long block with a `target:` key, a whole
  path under `tmpfs:`, and any of those written through a YAML anchor. **It resolves anchors**,
  because this tree writes one: the probe file names its mail root as
  `x-mail-root: &mail-root "/srv/mail"` and spends it inside `tmpfs:`, and a reader taking the alias
  for a path would report a leak on the one file that already got this right.
  `ComposeServiceError` is defined here, one refusal for both halves of the reader, since a caller
  catching it should not have to know which half raised.
- `composeservices.py` is `volumecheck.py`'s reader and has no CLI. It answers what each service
  runs, where it is built from, and which container paths it already covers; that last question is
  `composetargets.py`'s, split out of it under the line cap. It reads `image:`, `build:`,
  `volumes:` and `tmpfs:`, and groups everything by the service it belongs to. **`build:` is read
  in both spellings**, the short `build: ./brain` and the block carrying `context:` and
  `dockerfile:`, and `Service.build` carries the answer, because the row a built image is recorded
  under is only checkable against the file that builds it, and that mapping lives here and nowhere
  else. It used to be a bare flag set on meeting the key, so the block form's two keys arrived as
  service keys the walk did not recognize and were stepped over in silence. Like its two siblings
  it is a line reader rather than a YAML parse, these gates being stdlib-only, and it refuses every
  shape it was not taught rather than walking past it, a build key it has no answer for and a build
  block naming no context included. A service naming neither an image nor a build is read as a
  fragment, an override re-opening a base service, and the rule asks it nothing.
- `stubcheck.py [--root DIR]` ties the committed Rust seam stub back to the proto it was
  generated from (ADR-0003 stub-fidelity addendum). Both trees commit their generated stubs and
  regenerate them by hand with `just proto`, so a proto edit followed by no regeneration leaves
  the stub stating the old thing with every gate green, generated code sitting outside every
  other scan here. One rule: every comment `proto/body.proto`'s body carries, whether it stands
  on its own line or trails a field, must still appear as a doc comment in
  `body/crates/rpc/src/_generated/cortex.seam.v1.rs`, **in as many copies as the stub holds it**.
  Tonic writes each service into a client module and a server module and documents both from the
  one declaration, so a service comment stands in the stub twice and a reader opens whichever
  module they are working in; containment is satisfied by either copy, which is how rewording one
  of the two used to pass. The one text whose tally is pinned rather than counted is a rule line,
  which carries no words and whose surviving copies are not a function of the written ones, prost
  absorbing a banner's closing rule into the heading above it; its floor stays at one. It is a pure text comparison running no
  codegen, which is what lets it live inside `just check` at all, since regenerating the Rust
  half needs a system `protoc` that a clean dev box need not have. The comparison is over
  normalized text, `protocomments.py` undoing the three things prost does to a comment on its way
  into `///`: it escapes `[` and `]` so rustdoc does not read them as intra-doc links, it
  re-spells a setext heading as an ATX one so a service banner arrives carrying `##` markers, and
  it collapses a rule line of any length. **One direction only**, because the stub also carries
  doc comments tonic wrote about its own client and server, so the reverse containment is false
  by construction. **What it does not hold** is worth naming beside what it does: it is not a
  regeneration check, it sees no structural drift, which pyright and the Rust compile already
  make loud, and it reaches only the Rust half, the Python stubs carrying no comments at all to
  compare. That leaves the comment as the one silent case, and a real one, the proto's sentence
  about the body's default longest edge being copied verbatim into the file a Rust reader opens.
  **Fails closed**: a missing or unreadable input, a proto whose header cannot be told from its
  body, a comment shape the reader will not guess at, and either side coming back empty are each
  a failure rather than a quiet pass. Exit 0 with a summary stating what the comparison was over,
  the proto comments split by leading and trailing, how many of them a service claims two copies
  of, and the stub doc lines they were sought in; exit 1 printing `proto/body.proto:LINE: detail`
  per miss, each naming the copies found and the copies owed; exit 2 if `--root` is not a
  directory or an input could not be read.
- `protocomments.py` is `stubcheck.py`'s reader and has no CLI. It answers what a comment is on
  either side of the comparison and how the two spellings are made comparable. On the proto side
  it skips everything above `syntax = `, that header attaching to no declaration and prost not
  copying it, then collects leading and trailing comments while tracking string literals so a
  `//` inside one opens nothing, and refuses a block comment rather than guessing at it. It also
  records which comments a `service` claims, meaning those inside its block and the unbroken run
  standing directly above the `service` line, a blank line between the two detaching the run the
  way protoc does; those are the comments the stub owes two copies of. On the
  stub side it collects `///` lines and nothing else. `normalize` is the three-part undo above,
  applied to both sides so the rule is stated once.
- `samplecheck.py [--root DIR]` holds every log line a runbook prints back to an operator to the
  call site that writes it (ADR-0009 sample-membership addendum). A runbook that shows a rendered
  line is telling a reader what to expect on a stream while somebody is waiting, and nothing tied
  those samples to the `extra=` two hundred files away: a field a call stopped attaching left the
  sample printing what nothing emits, and a field it started attaching left the sample short of
  one, with both sides green. Four things have to agree per sample: the **level** the sample
  prints against the method the call uses (`exception` prints `ERROR`), the **logger** it names
  against the module that declares that name, the **message** against one a call there really
  writes, and the **fields** against exactly the keys that call attaches, in the order the
  formatter prints them. Field order is name order, so one comparison holds membership and order
  together, and it subsumes the neighbouring-field anchor the constant registry already carries
  over the same sample. **Values are deliberately not held.** A sample's values are placeholders
  as often as readings, one runbook's captured `port=50051` is registered in `crosscheck.py` as a
  dated reading rather than a coupling, and requiring a hand-written placeholder to be quoted the
  way the formatter quotes a value with a space in it is the fiction ADR-0009 refused to teach a
  gate to expect. **Found rather than registered**: the walk reads `docs/runbooks/` and checks
  every fenced line shaped like a rendered one, so a new sample is held the day it is written,
  and a runbook quoting a line no brain module writes is a miss rather than a skip. **Runbooks
  and not every document**, which is the other half of that decision: an ADR's transcripts are
  evidence of a run on a day, recorded beside the decision they justify, and holding a dated
  record to today's code would make the past a thing that must be edited to stay green. **Fails
  closed**: an unreadable runbook tree, a brain whose loggers cannot be collected, and either
  side coming back empty are each a failure. Exit 0 with a summary stating what the comparison
  was over, the samples, the runbooks and the loggers they were resolved against; exit 1 printing
  `docs/runbooks/FILE:LINE: the sample DETAIL` per miss; exit 2 if `--root` is not a directory or
  an input could not be read.
- `logsamples.py` is `samplecheck.py`'s doc side and has no CLI. It turns a fenced line back into
  the level, logger, message and field names it claims to render. A sample is a line **inside a
  fence**, never a sentence, since reading prose would make every inline mention owe a field
  list. The `LEVEL:logger:message` prefix is searched for rather than anchored, so compose's
  container label and the `#` that comments a sample out inside a shell block are decoration. The
  message stops where the first `name=` opens **outside a quoted value**, which is the rule a
  reader applies by eye and the only one that keeps a JSON argument from reading as a field. A
  sample that wraps over a trailing backslash is folded back into the one line it stands for,
  with the continuation's own comment marker dropped, because that marker would otherwise sit
  between the message and the first field; the fold stops at a fence so a backslash on a block's
  last line cannot swallow the marker that closes it.
- `logcalls.py` is `samplecheck.py`'s code side and has no CLI. It answers what one call puts on
  its line, and holds the reading of the brain's source that `loggernames.py` answers the other
  half over. It is the one reader here that
  **parses** Python rather than matching it: an `extra=` dict spans five lines at the failed
  settle, and a brace counter written to follow that is a Python parser with the corners missing.
  `ast` executes nothing, so the seam ADR-0009 declined to open, an import of the brain from
  `scripts/`, stays shut. A **message** is read in either spelling a module writes it in, written
  out at the call or handed to it by name, since the formatter renders the string and never the
  expression that carried it, so a page quoting the line cannot tell which the module wrote. A
  reader knowing only a literal said that the tool audit and the deep tier's spill watch log no
  such message, which is a fault about the document where the code is the thing that moved, and it
  fell on exactly the sinks a runbook has most reason to quote (ADR-0009 handed-message addendum).
  A bare name is resolved against that module's own top level, by `moduleconstants.py`, and nothing
  wider: a name from an import stays unmatched rather than chased, chasing one being the import
  this tree may not make, and a message assembled at the call is not one a page could quote at all.
  A module that binds a string **and** writes it again as the message of a log call is refused, the
  fault naming every binding of it, for the reason the one-name rule beside it gives: only the
  declaration is what the constant registry ties documents to, so the day the literal moves alone
  those documents restate a word the brain no longer writes (ADR-0009 one-message addendum). The
  domain is a log call's message rather than a name, which is what keeps the rule off a module
  that binds a sentence for a model to read and happens to log the same words. That rule runs over
  the whole tree rather than over the modules a sample names: `messages` walks every package's
  `src/` and `samplecheck.py` calls it beside the loggers, so a doubled spelling is refused the day
  it is written rather than the day a runbook quotes that line. Only each package's `src/` is
  walked, a package's tests sitting beside it. Fields come back sorted, which is not this reader
  rearranging an answer but restating `render_fields`, whose sort is what makes the printed order
  a function of the key set. The field list itself is read by `logfields.py`, described next. A
  message no call logs, a message logged twice, an `extra=` that reader cannot follow to a
  mapping written out and a key that is not a plain string are each reported rather than
  shrugged at, a shrug being how a gate hands itself an empty answer and calls the document
  right. One shape
  is refused **by name**: `logger.log(level, message, ...)` takes its level from a variable, which
  the model host's request failure does, so there is no level a sample could be held to, and saying
  that beats reporting a message the module visibly writes as one it does not.
- `logfields.py` is the field half of that reader and has no CLI, split off `logcalls.py` at the
  line cap. It answers which field names one call attaches, read off the call's `extra=` in
  three spellings: a mapping written out at the call, a bare name, and that name unioned with a
  mapping written out at the call (`extra | {"shortfall": ...}`), which are the spellings the
  brain writes. A name is followed inside the function the call is written in and no wider, to
  one binding at the top of that function's body above the call, and only when nothing else in
  the function names the binding: not a call on it, not a key set on it, not a rebinding in a
  branch, not a `global` or `nonlocal` declaration, and not a hand-over to any call that is not
  a log call. Under those conditions the mapping reaching the call is the one written out, so
  the keys read off the binding, plus those of the unioned literal, are the fields the line
  prints. Every other spelling is refused with a fault naming the line, because a field list
  read off a mapping something else may have changed would hold a document to a line nothing
  prints, which is worse than holding it to nothing (ADR-0009 composed-fields addendum). The
  tool audit's trail is the refused case in the tree: its mapping is bound, grown by `update`
  and by a key set under a condition, and only then handed over, so no one sample could print
  what it attaches, and it stays a line the tools runbook describes in prose. The rule for
  which calls are log calls is handed in by `logcalls.py` rather than read here, so this module
  carries no level table. Keys come back sorted and deduplicated, a key both halves of a
  union carry being one key on the record.
- `loggernames.py` is the other half of that reader and has no CLI. It answers which module owns a
  logger name, standing on `logcalls.py`'s walk of the brain's source, and it split off that
  module when teaching the message side its second spelling brought the file to the line cap, along
  the seam its own docstring had drawn from the day it landed. Logger names are collected from every
  spelling the brain uses,
  `getLogger(__name__)` resolving to the module's own dotted path (a package barrel claiming the
  package name), a literal being the name itself, which is the spelling no module here writes any
  more and which stays read because such a call is legal Python, and a bare identifier being a name
  the same module bound above the call, which is how both self-named sinks name themselves now that
  documents restate those names and the constant registry ties them to the declarations (ADR-0038
  named-logger and ADR-0009 audit-logger addenda). The third spelling is resolved against that
  module's own top level, by `moduleconstants.py`, and nothing wider: a name imported from
  elsewhere is refused with the name in the fault rather than chased, chasing one being the import
  this tree may not make. A name two files claim is a fault.
  A module that binds a name **and** writes the
  same string inside the call is refused, the fault naming every binding of it, because only the
  declaration is what the registry ties documents to and two spellings of one name are one edit away
  from documents tied to a name nothing writes (ADR-0009 one-name addendum). A module binding a
  logger name it does not pass is not reached by that rule, which sees two names rather than one
  spelled twice; what refuses it is this reader's own guard in `tests/test_loggernames.py`, which
  reads the self-named sinks off the tree, a logger that is not its module's dotted path being one
  by construction, and holds that set equal to the names brain modules bind under `_LOGGER_NAME`.
  Comparing two readings as sets holds every direction at once: a call passing another name, a
  declaration the call stopped passing, a sink naming itself with a bare literal and so leaving
  the documents no declaration to be tied to, and a sink binding its name under some other
  identifier, which is the naming the first set is read by and is therefore held rather than
  assumed. It names no sink, so a third is held the day it is written, and the identifier it does
  spell is a registered coupling tying it to both sinks and both module contracts (ADR-0009
  derived-sink addendum). That rule is a claim about this brain rather than about reading Python,
  which is why it sits in the suite and not in this reader: a reader refusing a bare literal would
  legislate over every fixture tree it walks, where what its own paragraph on that spelling is
  against is losing a logger in silence rather than reading one written legally.
- `rostercheck.py [--root DIR]` holds every roster a document keeps to the set it describes
  (ADR-0003 live-roster addendum and ADR-0029 roster-membership addendum). A **roster** is a list
  of names a page keeps for something the tree really holds: the `#[ignore]`d checks in the body's
  live seam suite, the modules in this directory, the two halves that same sentence sorts them
  into, the same set again in the repo map's fenced block, the tuples the constant registry is
  joined from.
  Each entry carries a sentence saying what its member proves or is for, which is why the list is
  written by hand and has to stay that way, and it is only the names that are held: **every member
  is named, and every name is a member**. The prose beside them is free, at any length and in any
  order, since a generated list could say what the names are and never what one of them proves.
  **Counts are not held**, and the live roster's opening tally came off instead: a number restated
  beside a list drifts before the list does and a reader can recount it in a second. **Where a
  roster begins and ends is data**, two phrases the document already carries, each exactly once,
  because several rosters share one page, one sentence closes one of them and opens the next, and
  a rule that read whole pages would let a
  name missing from one list pass on the strength of the other. Names are read in three shapes:
  as bullets,
  one per member with the name its first code span; as every code span in the passage matching
  the roster's own pattern; or **bare**, every whole word matching it, which is what reaches a
  repo map, a fenced block of plain text where a backtick would be a backtick and a match touching
  a word character is inside a longer word rather than a name.
  **A name a sibling roster owns is a reference and not an entry**, which is what lets one
  paragraph carry two rosters while saying whose reader each module is; nothing else is let
  through, so a module that gains a command line and stays in the second half is still a member
  the first half does not name. Exit 0 with a summary stating what the comparison was over, the
  rosters, the documents and the members; exit 1 printing `DOC: LABEL: DETAIL; WHY` per fault,
  which includes a boundary phrase that stopped appearing or started appearing twice; exit 2 if
  `--root` is not a directory, a document or a described set cannot be read, or either comes back
  empty.
- `rosters.py` is that gate's registry and has no CLI: every roster this repo has written down, as
  one tuple, in the same all-data-and-no-logic split `crosscheck.py`'s registry uses. An entry
  declares its label, its document, the two phrases bounding its passage, how a name is spelled
  there, what a member is, why the two sides must agree, the reader answering for the real
  set, and optionally the sibling set whose names that passage may carry as references. A roster
  arrives as one entry plus, when its set is a new kind, one reader; the scan never
  learns which document or which shape it is reading.
- `rosternames.py` is that gate's page side and has no CLI. `passage(text, opens, closes)` returns
  the run of a document a roster occupies, refusing a phrase the page does not carry exactly once
  and a closing phrase written before its opening one, since the boundary is part of what a roster
  claims. `names(text, written)` reads the names out of it, `Bulleted` taking the first code span
  of every bullet and refusing a bullet that opens without one, `Spelled` taking every code span
  matching the roster's pattern, and `Bare` taking every whole word matching it, for a passage
  carrying no code spans at all. A bare match is guarded on both edges, since the other two
  shapes get that from their own delimiters and this one would otherwise read a name out of the
  middle of a longer word. Fences are deliberately not read: a bullet inside one is read as
  a bullet, which fails loudly, and the alternative is a fourth spelling of the markdown fence in
  this tree.
- `scanrecipes.py` is which scans the single gate runs and has no CLI. Every other set a roster is
  held to is a listing of something; a cross-tree scan is not a file, so what makes a module one is
  that `just check` runs it before the per-tree checks and CI's `cross-tree` job runs it too.
  `gate_scans(text)` is the unbroken run of `just check-*` lines the `check` recipe opens with,
  `job_scans(text)` every `- run:` step of that job, and `recipe_module(text, recipe)` the one
  module a recipe hands to python, since the two names differ: `check-backlog` runs
  `backlogcheck.py`. **A disagreement between the two files is a fault rather than a merge**, since
  answering with either side alone would let a document agree with the half that had moved, and
  they are compared as sets, the order a scan runs in being each file's own business. A step it
  was not taught, a recipe running no module or two, and a missing recipe or job are each refused.
- `rostermembers.py` is that gate's tree side and has no CLI: the `#[ignore]`d tests in one Rust
  suite, read as the first function below each attribute so a stacked `#[tokio::test]` cannot hide
  the name; the file names in `scripts/`, whole and split into the ones carrying a top-level
  `if __name__ == "__main__":` guard and the ones that do not, which is the one fact deciding
  which half of this contract's opening sentence a module belongs in; and the registry's parts as
  the tuple names the
  `<subject>couplings.py` convention gives them, `couplings.py` itself being the vocabulary rather
  than a part. Every one of them refuses an empty answer, a comparison over nothing being one that
  cannot fail.
- `flagcheck.py [--root DIR]` holds every subagent server this repo starts to the flags its tier
  requires (ADR-0029 addenda on deriving the set a rule runs over and on covering both placements
  of one tier with one rule). **The rule is one and the readers are two**: this tier is started in
  two places, as a compose service and as the model host's own hosted tier, so the scan runs
  `REQUIREMENTS` over the union of `subagentservers.py` and `hostedtiers.py`. A flag added to the
  rule therefore reaches both placements the day it is written, and a flag renamed on either side
  fails, the sidecar's own spelling being compared against this one rather than trusted.
  `REQUIREMENTS` is the rule
  and it is production code here: each entry carries a label, the sentence saying why every server
  must meet it, and the flags it is made of. Two entries today. **The membership both readers
  decide is held too**, by a second rule in the same scan: every model artifact the tree names
  must be named under a `CORTEX_MODEL_FILE_` variable, since that spelling is the whole of what
  makes a server or a tier classifiable, and one named another way would leave both sets in
  silence. Its domain is deliberately not the family, which would be a rule about the convention
  it checks and could not fail for the fault it exists to catch, but every artifact
  `artifactnames.py` finds structurally. The reasoning-off pair is **one**
  requirement rather than two, because two flags that must travel together are one claim about a
  deployment and a fault should print the reason whichever half went missing; the tool-capable
  chat template is the other, a server without `--jinja` coming up healthy with no tools at all.
  A flag carrying a value is held at **every** occurrence rather than the first, llama.cpp taking
  the last spelling of a repeated flag, so a server whose second `--reasoning-budget` disagrees
  with its first is a fault rather than a pass. Both floors are asserted, a rule requiring nothing
  and a tree starting no server each being a scan that reports success forever. The count under
  `--reasoning-budget` is one value in two trees, this rule's and the model host's
  `_NO_REASONING_BUDGET`, and `crosscheck.py` is what holds them together.
- `subagentservers.py` is the compose half of that gate's set and has no CLI. `servers(root)`
  returns every subagent
  server the compose tree starts, and the derivation is the deliverable: **the set is read off the
  stack rather than registered beside the rule**, so an override adding a server is held the day
  it is written. A service is one for either of two reasons, and each catches what the other
  misses. The wiring says so, an environment value under `CORTEX_SUBAGENTS_ENDPOINT`,
  `CORTEX_SUBAGENTS_GPU_ENDPOINT` or a `CORTEX_SUBAGENTS_ROSTER__<name>` object writing an address
  whose host is a service name; or the argv says so, the command naming its model file under a
  `CORTEX_MODEL_FILE_SUBAGENT*` variable, `MODEL_PREFIX` being the single place that prefix is
  written and `FAMILY_PREFIX` beside it the string it is built from, which is what the naming rule
  holds every artifact to. The image is deliberately not part of the answer, the
  CPU embedder running the very same llama.cpp image, and a service declaring no command of its
  own is not one, its argv belonging to an entrypoint or to the model host's supervisor, which the
  other half of the set reads directly.
- `hostedtiers.py` is that other half and has no CLI. `hosted(root)` returns every tier the model
  host starts as a subagent, read off `brain/packages/model_manager/src/cortex_model_manager/`:
  the flags out of `llama_server_argv`'s own return tuple, the tier's tail out of the `extra` its
  `TierArgs` declares, spliced in where that builder splats it. **A tier serves subagents when the
  setting naming its artifact does**, the same `CORTEX_MODEL_FILE_SUBAGENT*` reading the compose
  side makes, taken from the field's `validation_alias`; the tier's logical id is deliberately not
  the test, an id being what a deployment renames. Nothing about which flags matter is written
  here, which is what keeps the rule single. An argv item it cannot reduce to a string becomes
  `UNREADABLE`, a token no requirement can be met by, since dropping it would close the gap
  between a flag and the item after it. Everything it was not taught is refused rather than
  answered emptily: an absent or unparseable module, a builder that does not splat a tier's tail
  exactly once, a settings class naming no environment variable, a tree declaring no tier at all,
  a tier whose artifact path names no field it can resolve, and a subagent tier whose own tail is
  a call rather than literals. `tier_artifacts(call, named)` is the same walk with that subagent
  filter off, which is how one declaration serves both the membership reading and the naming rule
  above instead of being read twice.
- `artifactnames.py` is what those two readings rest on and has no CLI. `named(root)` returns every
  model artifact the tree names, with the file, the service or settings field, the line and the
  variable, and `flagcheck.py` holds each to the family prefix. **The artifacts are found
  structurally, in both languages, each read for the mechanism that carries a file to the engine
  in that language**: a compose one is the item after one of llama.cpp's own file flags,
  `ARTIFACT_FLAGS`, which are `--model` and `--mmproj`; a hosted one is the settings field a tier
  reads its `model_path` from, or any settings field the sidecar hands to its resolver, `_path`,
  the one method that joins a file onto `models_root`. `resolved(module)` is that second reading,
  and it exists because `model_path` is one keyword of several that carry an artifact into an
  argv: the multimodal projector rides the cortex tier's `extra`, assembled by a call the tier
  reader refuses to approximate, and the flag in front of it is written on a local bound one
  statement earlier, where the resolver call is handed the field directly. Until 2026-09-02 that
  reading was the field's own name ending `_file`, which found the projector and would have found
  nothing under `cortex_mmproj_path`; a name is what an author picks and a resolution is what the
  module does (ADR-0029's addendum on the artifact domain being the resolver). The domain is the
  Python side and never the environment variable, that being the spelling under test, and a field
  found both ways is one artifact reported at the tier that spends it. Reading only the variables
  that already begin `CORTEX_MODEL_FILE_` would have been a rule whose domain is the convention it
  checks, unable to fail for the misspelling it exists to catch. Two shapes are **refused** by
  name rather than read around: a settings method other than the resolver reading `models_root`,
  which would be a second resolver joining a path by hand, and a resolver handed no field at all,
  which is the floor, since a renamed resolver takes every call with it and the tier reading would
  otherwise go on finding three artifacts while the projector dropped in silence. Two exclusions
  are deliberate and each is what a fault would otherwise be wrong about: the **short** spelling
  of the model flag is not read, this tree starting an MCP sidecar with `python -m <module>` and a
  reader of `-m` calling that module an artifact; and an item spending **no variable** carries no
  name to misspell, and the wiring is what finds such a server. A third one was retired when the
  CPU embedder was renamed into the family: an argv declaring `--embeddings` serves no chat, which
  is the membership reader's question and not this one, so what a server serves no longer excuses
  an artifact from being spelled findably (ADR-0029's addendum on a non-chat artifact naming
  itself in the family). The engine has file flags beyond the two read here (a draft model, a LoRA
  adapter), and a compose service spending a variable after one of those is unread until the flag
  is added; `hostedtiers.py` asserts its own floors underneath, refusing a sidecar with no tier and
  a tier with no artifact.
- `moduleconstants.py` is that reader's syntax side and has no CLI. `constants(module)` returns
  every top-level string and run of strings a parsed module binds, `parse`, `text`, `items` and
  `bound` being the pieces it is built from. Parsed with `ast` and never imported, for the reason
  `logcalls.py` gives: a tuple of flags is written over as many lines as it has items, and a
  reader following that in text is a Python parser with the corners missing. Resolution runs in
  source order, which is what makes a name resolvable and a cycle impossible. Two answers that
  look alike are kept apart: a value that is no sequence at all comes back as `None`, and a
  sequence one of whose items is unreadable comes back as a sequence holding one, since a caller
  conflating them would report a tier's whole tail as empty rather than as unreadable.
- `composestarts.py` is that reader's compose side and has no CLI. `read_starts(text)` returns
  every service one file writes, with the argv it starts with and the environment it is given,
  which are exactly the two keys `composeservices.py` steps over. A command of `None` is a service
  that says nothing about its own argv, which is the normal shape for an override re-opening
  `brain:` and is a different answer from an empty command. Both keys carry a block scalar in this
  tree, a shell line folded into a command item and a JSON object folded into an environment
  value, so both are read by one pair of methods and closed at the first line no deeper than the
  opener. Every other shape is refused rather than stepped over: a command that is neither an
  inline list nor a block of items, an inline or list-form environment, an inline service body,
  and a line indented under no service.
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
  `bucket` it files under, so nothing downstream re-derives a state from prose. **A field wraps
  like the prose around it**: its continuation lines are joined with a single space and the block
  ends at a blank line, the rule markdown uses to end a paragraph, so a long value cannot render
  truncated mid-sentence in the index. Inside that block a line starting with `**` is a field or
  an error, never a continuation, which is what keeps a field line missing its colon from being
  absorbed into the value above it (ADR-0039 wrapped-field addendum).
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
  with a `#` inside a fenced block not counted as a heading. `local_targets(text)` returns each
  in-repo link as a `Target(line, path, fragment)`, so a problem names the line it is written on.
  `check(root, indexes)` walks every markdown file under `--root`, skipping the directory
  components `dashcheck.py` skips for the reason that gate gives, and reports any fragment that
  names no heading the document it aims at offers; a pointer with no path is aimed at the document
  it is written in, which is how an index's links to its own hand-written sections are covered.
  **A backlog index answers out of the spliced index**, the hand-written halves around the freshly
  rendered block, and never out of the committed file: a stale index is then judged as the document
  it is about to become, and its staleness stays one problem instead of a hundred. An index whose
  rendering this run could not work out is registered with `anchors=None`, which skips every
  pointer at it rather than reading the stale file. **Every other target answers out of the file on
  disk, and only if this same scan read it** (ADR-0039 repo-wide-anchor addendum): one list decides
  which markdown is this repo's prose, for sources and targets alike, so nothing vendored or built
  is ever asserted about. A markdown target the scan did not read is a reported problem, missing,
  outside the tree and vendored being the three causes; a target whose name is not markdown is
  outside the question, `body.proto#L42` being a line anchor with no headings to be wrong about.
  **A document carrying a heading `headingshapes.py` refuses is registered with `anchors=None`
  too**, for the reason the broken index is: its anchor set is unknown, so nothing aimed at it is
  judged and the run is already failing on the heading.
- `headingshapes.py` is what a heading is to that scan, and the one place the gate says out loud
  what it claims about rendering (ADR-0039 slug-fidelity addendum). `headings(text)` returns every
  ATX heading outside a fenced block with its line number, which `anchors()` reads. The slug rule
  is applied to a heading's **source**; a renderer slugs its **rendered** text, and the two agree
  exactly when every construct in the source is built from characters the rule already drops and
  carries no text away: plain prose, punctuation, code spans and `*` emphasis all qualify.
  `unsluggable(text)` returns the six shapes that do not, each as an `Unsluggable(line, heading,
  reason)`, and `problems(name, text)` renders them for the gate. The six are a bracketed span,
  angle-bracket markup (an HTML tag or an autolink), a closing run of hashes,
  underscore emphasis, an entity reference, and a setext underline, which is the one that is
  invisible rather than misread. **The bracketed span is refused with or without a target**
  (ADR-0039 bracket addendum), which covers an inline link, an image and both reference forms by
  the mark they carry and the shortcut form, which carries none: whether that one is a link
  depends on a link reference definition elsewhere in the document, the one question a heading
  cannot answer about itself. The price is a literal pair of brackets in a heading, and no heading
  in this tree spends one. **They are refused, not emulated**: rendering a heading's inline
  markdown before slugging it is a transform written against shapes the tree does not contain, and
  a wrong transform yields a wrong anchor, which is a silent accept nothing here could see, where a
  refusal is loud. An underscore *inside* a word is never reported, CommonMark reading none as
  emphasis, and neither is a link quoted inside a code span, whose backticks come off on both
  sides.
- `coverage_gate.py PATH --rustc TEXT --llvm-cov TEXT` reads a
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
  **Both relays are required arguments** (ADR-0002 mandatory-relay addendum): a run missing either
  exits 2 on argparse's usage error, having printed no verdict at all. They were optional once, and
  the producer cross-check is the half of the attribution that can fail, so deleting `--llvm-cov`
  from the recipe deleted that check while the run still printed a full green verdict and exited 0.
  Verdicts print in order: the attribution lines (`measured by ...`), then one `PASS`/`FAIL` line
  per metric.
- `ci_paths.py` implements AGENTS.md gate 3 / ADR-0006. Decides which toolchain CI jobs must run
  for a set of changed files. Reads newline-separated repo-relative paths (the output of
  `git diff --name-only`) on stdin; blank lines are ignored. Each path is classified by
  ordered rules, first match wins (the normative rule list lives in ADR-0006); the
  result is the union over all paths. Writes exactly four `GITHUB_OUTPUT`-format lines
  to stdout, in order: `python=true|false`, `rust=true|false`, `overlay=true|false`, then
  `shell=true|false`
  (the overlay = the `body/app/` React tree, gated by `check-overlay`; its Tauri shell
  subtree `body/app/src-tauri/` is Rust and is carved off the overlay to the `rust+shell`
  verdict, which sets `rust` for that subtree's fmt check inside `check-body` and `shell`
  for the separate webkit-carrying job that runs `check-shell`), and nothing else.
  Logs one `ci-paths: PATH -> VERDICT` line per path to stderr so CI logs show why a job
  ran. Empty input yields all four `false`. Unmatched paths fail closed to ALL four
  (unknown means over-test, never under-test). Always exits 0, because classification has no
  failure mode. `shell` is the one output no other job reads, so a rule that forgot to set it
  would leave that job unrun and looking green; two tests hold the routing from both sides.
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
  and, in the tests, staged a fixture file into the in-flight commit's own index. That
  strip is `gitenv.py`'s and no longer this module's, along with the reason for it; what
  stays here is the policy above, a git this gate cannot run leaving the commit unblocked.

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

- `trailwidth.py CAPTURE [CAPTURE ...] [--resamples N] [--seed S]` is the second module here that
  gates nothing, and it is here for the same three reasons: pure, never inside the brain image,
  covered like everything else (ADR-0038 real-trail addendum). It reads captured log text and
  reports the rendered width of the recall trail's `dropped` field, which is the widest value the
  tree attaches and therefore the value `cortex_core.VALUE_CHARS` is argued against. A line
  qualifies by carrying the trail's own message and that field, and **both of those words are
  registered in `logcouplings.py` against the sink that writes them** (ADR-0038 tied-needle
  addendum), so a rename in the brain fails `just check` on the day it is made rather than
  surfacing here weeks later as a capture holding no trail line at all. **The whole line that field
  sits on is reported beside it**, in the same cohorts, because the per-value bound leaves the line
  itself unbounded and the recall trail is the widest line the brain writes (ADR-0038 whole-line
  addendum). That width is measured from where the shipped formatter's output starts, the level,
  logger and message of `logging.BASIC_FORMAT`, so a capture's own service prefix is not counted
  and the two captures a run takes are comparable; finding that opening is also what qualifies a
  line, which is what tells the message from the logger name ending in the same word. The rendering
  is taken from the field's `=` to the next `name=` pair rather than to the next space: the trail's compact JSON holds
  no space, but a rendering the bound CUT ends in a marker that carries two, and stopping at the
  first of them would report a cut field as a whole one exactly at the bound. Per capture it prints
  the count, the floor and ceiling, the median, and a seeded percentile bootstrap of the mean, then
  the same shape for the whole line without an interval, since a mean's sampling distribution says
  nothing about the ceiling a line is read for, then the range over every capture and how many
  renderings were cut. **The cut count is the load-bearing
  line**: any number above zero says the bound bit a value that ships. Refuses rather than guesses
  on a capture it cannot read, one holding no trail line at all, and a non-positive resample count.
  Exit 0 printing the report; exit 2 printing one `trailwidth: PROBLEM` line; argparse exit 2 on
  usage.

- `envelopefloor.py SAMPLE [SAMPLE ...]` is the third module here that gates nothing, and it is
  here for the same three reasons (ADR-0028 control-arm addendum). It reads the per-arm samples
  `brain/packages/orchestrator/tests/test_envelope_cost_live.py` writes and publishes what each arm
  did, but only while the arm every rate is read against still stands: **the control arm is the one
  carrying no grammar and no appended sentence, and a comparison read against a control that failed
  the subtask prices the pick and not the envelope.** That arm answered 96 of 96 on three picks of
  the subagent row and then 93 and 92 on two more, so it is a reading and not the constant the
  record had begun quoting. **Two rates describe one run and both are published.** What a run
  **stood** is the weaker of them: the runner accepted it, the reply is not empty, and it is not
  the instruction handed back, which are the three failures visible without knowing the subtask.
  What a reply **delivered** is judged against the subtask by `envelopejudges.py`, which is where
  the judging the ADR-0028 addenda did by hand now lives (ADR-0028 judged-delivery addendum): a
  judge is declared **per subtask shape**, beside the instruction it belongs to, and a run belongs
  to a declared shape when its instruction opens with that shape's, since the constrained path
  appends its sentence last. A shape no judge is declared for, which is what a hand-typed
  `CORTEX_ENVELOPE_INSTRUCTION` produces, publishes `stood` alone and says so by name rather than
  being guessed at. Under the tabled reading below, `stood` still bounds `delivered` from above.
  **The three arbitrations are stated columns rather than defaults**, `--comma`, `--refusal` and
  `--naming`, each printed in the report beside the rates it produced: how a comma between digits
  reads, whether a refused run is a non-delivery whatever its text held, and whether a garbled
  naming of a reporting period counts. The floor is **nine tenths of a
  cell's own runs**, argued rather than measured (this row's envelope arms have gone as low as 66
  of 96, so a control under nine tenths is doing no better than the arms it exists to explain), and
  it is held **per subtask shape**, a shape being the instruction a run was given, since a pick
  that answers a summarization and cannot do an extraction has one cell at ceiling and one on the
  floor. The rule is **one-sided so that a red is a proof**: a cell is refused only when its Wilson
  95% interval lies wholly under the floor, which is 25 of 32 or worse on a swept cell, 80 of 96
  pooled, and a four-run probe only once half of it has failed. That interval is the same arithmetic the ADR-0028 tables
  publish beside every rate, and ten of those published intervals are reproduced by the suite here.
  There is deliberately **no `--floor`**: a floor with a knob beside it is a suggestion, and the
  one reader who would reach for it is the one whose control arm just failed. **Both rates are
  held to that floor and both verdicts are taken under the tabled reading**, the column the
  ADR-0028 rows are in, whatever columns the three flags asked to be shown, so a flag moves what a
  reader is shown and never what the tool publishes; `delivered` is held only where a judge is
  declared, and where none is the cell is still held on `stood`. Which arm is the
  control is read off the sample's own `control` field rather than off an arm's name, so no name
  has to agree across the two trees, and every other drift in that format is loud: a renamed or
  dropped key is a refusal naming the key, and a run whose arms all say they are not the control
  is refused as no comparison at all. Exit 0 printing the report; exit 1 printing it with a
  `refused:` line (no control arm in the samples, or a cell proven under a floor); exit 2
  printing one `envelopefloor: PROBLEM` line; argparse exit 2 on usage.

- `switchtail.py SAMPLE [SAMPLE ...]` is the fourth module here that gates nothing, and it is here
  for the same three reasons (ADR-0005 rendered-tail addendum). It reads the per-tier samples
  `brain/packages/inference/tests/test_thinking_switch_live.py` writes, with `switchsamples.py`
  answering for that format, and it holds one rule two documents carry: **a tier whose chat
  template answers the thinking switch by rendering a thought already closed holds that switch
  under a `response_format`, and one whose answer leaves the thought open does not.** The rule is
  eleven readings of one engine build's handlers rather than a theorem, each of the eleven now
  published through this reader on `b10680-d7bd3bfca` (ADR-0005 lineup-tails addendum), so the
  report names and measures a tier that breaks it instead of the live run going red on the reading
  that found it.
  **The reading is on the tail**, taken after the last of the ask the driver recorded sending,
  because the failing pick's two prompts differ by a whole system turn at the front and end byte
  identically: comparing renderings for difference sorts nothing. A closed thought is `</think>` on
  the native family and `<channel|>` on gemma-4, a vocabulary no endpoint offers and a probe run by
  hand may hold, so every verdict prints the tail it was read off. **An unmarked tail is two tiers
  and the key says which**: the failing pick answers by dropping a system turn at the front, so its
  switched tail is byte identical to the one rendered with the key left alone and leaves the
  thought open, while an unmarked tail the key **changed** is an unrecognized format and is refused
  rather than read as open (ADR-0005 third-spelling addendum). That comparison is on the two tails
  and never on the two renderings, for the same reason the reading is. The two sides are **not
  equally strong and the report says which it is
  on**: a closing tail is refuted by one deliberating draw, an open one only by a whole cell that
  never deliberated. Nothing is published from a constrained cell drawn under five times, the
  probe's own rule (that cell splits 4 to 1 on a shipped pick), nor from one whose control arm, the
  same request with no switch, failed to deliberate on every draw. **That last refusal is worded
  off the tail rendered with the key left alone**, which the report has already printed: a tail
  closing the thought with a listed marker names the template as what left the control nothing to
  deliberate in, an open one names the prompt, and an unmarked one names the two readings the tail
  alone cannot separate, a prompt inviting no thought and a closing marker this reader does not
  list (ADR-0005 quiet-control addendum). Which cell is constrained and which sent the switch are
  the sample's own flags, so no shape's name has to agree across the two trees. **The report's
  first two lines name what the operator pointed the probe at and what the server said of
  itself**: the sample's `build_info` and `model_path`, read once off `GET /props` and required by
  name like every other field, so a row copied into a record names the engine build and the file
  it was measured on off the page rather than off the driver's notes, and a quant the lineup does
  not name is visible there (ADR-0005 served-by addendum). Exit 0 printing the report; exit 1 printing it with a `refused:` line (a rendering it
  cannot place, a tail in a spelling it cannot read, a cell too thin to read, a control that did
  not fire, or a prediction the measurement broke); exit 2 printing one `switchtail: PROBLEM` line;
  argparse exit 2 on usage.

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
  the flag used to do here; the sweep over other orders is `just shuffle [seed]`, which
  `.github/workflows/shuffle.yml` runs weekly and on demand since the same ADR's sweep-schedule
  addendum. That workflow is the one in this repo that is not the `just check` mirror `ci.yml` is:
  it runs a committed recipe like every other job, but it gates nothing and is required by
  nothing, which is what makes an order nobody chose safe to run at all. It draws the seed itself
  and refuses one that is not digits, since the dispatch input is typed text; the seed and the
  `just shuffle <seed>` that replays it reach the run summary before the sweep starts, so a
  cancelled run still names the order it was drawing.
- `crosscheck.py`'s registry is checked against the real trees by its own suite
  (`test_the_repo_itself_is_tied`), so `check-scripts` catches a drift even when
  `check-crosscheck` is not the recipe that runs. The same suite reads the registry against the
  brain's log calls:
  `test_every_registered_binding_a_brain_log_call_is_handed_is_held_at_that_call` requires, of
  every registry site a brain log call is handed as its message, a mention on that sink rendering
  the name and landing on the call's line, a set read off the registry and `logcalls.handed`
  together rather than off any naming, a message having no `_LOGGER_NAME` to be found under
  (ADR-0009 held-call addendum). Registering a constant in a language
  `DECLARATIONS` does not know, or a mention whose template renders nothing the registry fills, or
  one whose name and whose `{name}` do not both appear, or an entry whose places are all on one
  side of a seam, a side being a language together with the brain package under
  `brain/packages/<name>/`, is refused by that suite too. It used to refuse an entry
  confined to one top-level tree; the overlay and its stylesheet are one tree and two languages,
  so suffix replaced tree when mentions landed; then the email sidecar's own texts and its
  declared-source key, each held between two brain packages that cannot import each other, put
  the package beside the suffix (ADR-0029 run addendum). Two more invariants guard the widening
  itself: the
  registry must exercise every `Relation` member and both kinds of place, since a comparator no
  entry uses is a gate that cannot fail. `test_the_registry_pins_at_least_one_occurrence_count`
  and `test_the_registry_spends_at_least_one_rendered_name` hold the two newest fields to the same
  rule, a field no entry sets being a dead wire, and
  `test_the_registry_reduces_every_form_the_reducer_was_widened_for` holds the decimal, the boolean
  and the signed integer to it, a form the
  real tree never spells being unexercised in exactly the same way, and
  `test_the_registry_exercises_every_spelling` holds `Spelling` to the rule `Relation` already
  answers to. `test_the_parts_on_disk_are_exactly_what_the_registry_reads` guards the split itself:
  it globs the
  `*couplings.py` files rather than reading the same import list that would be wrong, so a part
  nobody added to `registry.py` fails instead of gating nothing in silence. It runs **both
  directions** (ADR-0029 registry-equality addendum): the union of the parts must also be everything
  `CONSTANTS` holds, so a `Constant` written inline in `registry.py` fails naming its label rather
  than gating normally under none of the names the docstring lists. Beside it,
  `test_the_registry_holds_each_coupling_once` asserts that no label appears twice, which is how the
  count is held: an entry in two parts leaves the verdict alone, the scan asking one question twice,
  and makes `shape.entries` count a collection the registry does not have. The convention a part is
  found by, a `<subject>couplings.py` holding a `<SUBJECT>_COUPLINGS` tuple, is asserted in the
  helper both tests go through, so an export under another name is a sentence rather than an
  `AttributeError`.
  `test_registry_names_every_part_in_the_order_it_reads_them` guards the other half of a split, the
  prose (ADR-0029 registry-parts addendum): the parts are named in `registry.py`'s docstring and
  nowhere else, so the bullet names are read back out of `registry.__doc__` and required to be the
  files on disk, in the order `CONSTANTS` joins them. A part read but unnamed passes the glob and
  fails this, which is the one shape a directory listing cannot see.
- **Which far sides a compose default gets registered against** was settled by reading every
  `${CORTEX_*:-default}` under `docker/` (ADR-0029's compose-default survey addendum). A
  substitution is registrable only when some tree **declares** the same value, which is why the
  survey hoisted several numbers out of `Field(...)` calls into module constants beside the fields
  they default; a default that appears only in compose files has nothing to disagree with and is
  deliberately left alone, since a scan over it would assert that a file agrees with itself.
  Outside `docker/`, a restatement is a far side when it becomes **wrong** as the value moves (a
  runbook's env row, a stated default, a module contract) and is not one when it becomes
  **history** (an ADR, a measurement record, a dated log line), which is the same test that has
  always kept ADRs out. **A comment inside a compose file answers to that test and to nothing
  else** (ADR-0029 comment addendum): it is no new form and no new spelling, only another place a
  whole value appears, reached by the mention template the runbook sentences already use. Four are
  registered: the two halves of the measured legibility pair that name the other file's number
  (`CORTEX_IMAGE_MAX_TOKENS=1024` in the body override, `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` in the
  GPU one), because the pair is what either number is for, and the two that name their own file's
  default a few lines above the substitution carrying it.
- **The legibility pair was then read out of prose the same way** (ADR-0029 legibility-prose
  addendum), which is what turned two entries with three and four far sides into two with ten and
  thirteen. Held: the module contracts stating either default, the GPU runbook's env table **and**
  the recipe block under it, the vision runbook's three claims about what ships, both declaring
  files' own prose beside the constant, and the host check telling an operator what a stock
  deployment captures. Left out: every measured arm, cost and reservation row, each of which was
  measured **at** a value and goes on being true after it moves. The needle carries that sort where
  it can: the recipe block is pinned at a line start, `"\nCORTEX_IMAGE_MAX_TOKENS={value}"`, because
  the measured table below it writes the same text inside a cell, and the vision runbook's three are
  pinned by count because a file naming two different shipped budgets is a defect rather than a
  design change. The edge gained a second **site** in the other tree, `BRAIN_EDGE` in
  `body/crates/core/tests/capture_bytes.rs`, which is what the byte-ceiling headroom suite measures
  against and is a fixture that has to follow the brain rather than a value it may choose.
- **The body's bind port was read out the same way** (ADR-0023 port-prose addendum), which took one
  entry from five far sides to twenty three. Four needle shapes carry that sort, so none of them
  pins the phrasing around the number: `default 127.0.0.1:` for a stated bind,
  `CORTEX_BODY_ADDR=0.0.0.0:` for the export the container path needs, `host.docker.internal:` for
  the endpoint the brain dials, and the declaring module's own two doc comments. The shapes do the
  excluding: the volume runbook's record of a fake server once served on that address writes the
  address alone and so is reached by none of them, which is right, a dated reading being history.
  Three wiring tests are out for the other reason, each setting `CORTEX_BODY_ENDPOINT` to a string
  and asserting the composition root read it back, which any port would pass.
- **The brain's own seam port went the same way** (ADR-0023 seam-port-prose addendum), which took
  the entry the body's port had been modelled on from four far sides to twenty three, over twenty
  six spellings in eighteen files. The gap was not the one the backlog recorded as prose only:
  eight of those spellings are code. `brain/Dockerfile`'s `EXPOSE`, the tonic client's dial
  example, the Rust live suite's stated default beside the fallback it uses, the body server's doc
  comment naming whose port this is, the body override's comment beside it, and two
  `integration`-marked live suites were all loose. Two kinds stay out, and each names a rule. The
  WSL runbook's `port=50051` is a captured line of server output shown to explain how a log
  renders its fields, so it is a dated reading like the volume runbook's address. And
  `test_config.py` asserts this very default three times while needing no gate at all, which is
  where the line falls between a suite that holds itself and one this scan has to hold: a unit
  test fails the moment the constant moves without it, where an `#[ignore]`d measurement or an
  `integration`-marked live test drifts in silence until somebody next measures. That is the same
  line `capture_bytes.rs` sits on, promoted to a site for exactly this reason.
- **A second spelling on an already held line gets its own needle, and the scan learns nothing new**
  (ADR-0029 second-spelling addendum). A mention is a presence check, so a line whose first
  spelling a needle reaches can carry a second that drifts freely. The population was measured
  before anything was decided, by rendering every needle in the registry and counting the value's
  bounded occurrences left over on each line it matched: eleven readings over nine lines, of which
  six were artefacts of the reading (an identifier that happens to spell a string value, two lines
  held jointly by two needles each and so counted twice, and a decimal whose whole part sits
  inside a measured latency, an artefact the decimal-edge close above has since removed from the
  matcher), leaving five real ones. **One of those five is deliberately not a far side**, the vision runbook's second `auto`,
  which says what that mode DOES beside what `on` and `off` do and stays true after another mode
  becomes the shipped answer. That single case is what refused a mechanism: counting a value's
  occurrences per line, whether as a field or as a rule, would manufacture a coupling the tense
  test rejects, and it cannot be told the difference. Rewording the prose was refused as the gate
  editing what it watches. So the four real ones became four ordinary mentions, and the objection
  that such a needle must carry words of a sentence was already answered by the tree, which had
  been holding `` `1024` is the default, paired with `` since the legibility sort. Two of the four
  are the more dangerous form, where the needle held the Meaning cell's explanation and left the
  **Default cell** free.
- **A derived literal is a consequence of a value, not a spelling of it, and no row may hold one**
  (ADR-0029 second-spelling addendum). The headroom suite asserted a resampled size as the pair
  `(2048, 1152)`, where the width is the capture edge and the height is that edge times the
  fixture's own aspect ratio. Retune the edge and the Rust suite fails with two numbers nothing in
  the file explains, while every gate here stays green, so the pull to register it is real. It is
  still wrong: a needle over the pair would tie the edge and the fixture's display shape into one
  answer and would fail when the fixture changed, naming a coupling that never moved. So the
  suite computes the size from the constants it already declares, which **removes** the coupling
  instead of holding it, and the same reading keeps the halved `1024` in that file's prose out,
  a rung of the ladder below the edge being a consequence too. Proved both ways on the real tree:
  retuned to 1800, the literal pair fails the case with `left: (1800, 1012)` against
  `right: (2048, 1152)` and the derived one passes.
- **There is deliberately no coverage reading over this registry** (ADR-0029 census addendum). The
  scan says every place it names still agrees and cannot say it names every place, and four sorts
  in a row corrected their own count of the tree upward by hand, so a census was asked for as
  either a gate or a report. It was measured before it was designed, over the registry as it then
  stood, and both honest scopings failed. Rendering each registered value and counting its bounded
  occurrences across every tracked text file returns **37,717** occurrences no needle covers,
  because `brain` and `cortex` are words, `2` is a number and `False` is a keyword. Narrowing the
  candidate set to files that also spell the constant's own identifier returns **927**, of which 34
  belong to an entry that had just been sorted exhaustively an hour earlier. A gate would need an
  acknowledged-exclusions list of either size, which is a second registry nobody maintains, and a
  report at either rate is the listing nobody reads that the request itself named as the failure.
  What replaces it is a **method**, and it is written down because it cannot be a tool: sort by the
  **name** a value is spelled under, never by its digits, then read each hit against the tense test,
  which is the judgement no scan makes. The one scoping that did measure well, counting a value's
  leftover occurrences on lines a needle already matched, is the second-spelling reading above, and
  it found and closed its own population.
- **The one reading over the registry that IS worth having is its own shape** (ADR-0029
  registry-shape addendum), and it is printed and never asserted. The census above declines a
  reading over the tree; this is the reading over the registry, and it costs one walk of a tuple
  the scan already walks. What made it worth building is that the numbers were being counted by
  hand: this document's tally of how many mentions carry a count was corrected three times in one
  day and its account of how many files the registry is written in twice, and on the day it was
  built the tally was stale again, saying seven prose-sort additions where the registry held eight.
  Nothing asserts the shape, and that is the decision rather than an omission. A gate holding this
  document to the registry would tie the gate's own prose to the gate's own data, which is the
  exclusion the legibility sort wrote down and which a document describing the gate has always had.
  So the hand-counted tallies left this document instead: the counts above are the scan's to print
  and this doc's job is which mentions are counted and why. **The one number that stayed uncounted
  is the parts** (ADR-0029 registry-parts addendum), and a fifth integer beside the four, or a
  named mapping from part to its own `Shape`, were both weighed and declined. Nothing in the scan
  depends on how many files the data sits in; a lost part already moves the entry count, and the
  thing that **fails** on one is the suite reading the directory rather than any number; and the
  mapping's second benefit, a fault naming the part its entry came from, costs the scan's blindness
  to which file an entry sits in to save a reader one grep, every label being distinct. What the
  parts get instead is the named list in `registry.py`'s docstring, held complete and in read
  order by the suite, which answers the count and says what each part is for in the same place.
- **Every cross-tree scan states the collection its verdict is over** (ADR-0029 addendum on the
  other four gates), which generalised the reading above to all six. The rule is that a success
  line naming no collection is equally true of a scan that read nothing, so each gate prints what
  its own walk read **after** its exclusions: files and lines for the line cap and the dash ban,
  compose files, binds and landings for the bind check, compose files and variables beside the
  variables actually compared for the defaults check, the registry's four-part shape for
  `crosscheck.py`, and a count line per backlog for `backlogcheck.py`. Every one of those numbers
  is a reading and **nothing asserts any of them**, here or anywhere: the suites pin that a gate's
  counts count different things, over fixtures built so no two of the numbers coincide, and pin no
  number the live tree holds. **The floor is the exception and is a gate**, because "at least one
  file was read" is a fact about the walk rather than about the tree: `linecap.py` and
  `dashcheck.py` exit 2 on a walk that measured nothing, which is the rule `composefiles.py` has
  always given the two compose gates. The deeper counts get no floor, a compose file declaring no
  bind and a variable spelled once each being ordinary.
- **A value a needle carries as a literal is SHADOWED, not held** (ADR-0023 bind-host addendum).
  Two dozen templates across the two endpoint entries spell `127.0.0.1`, which reads like the
  loopback address being tied in two dozen places. It is not tied anywhere by them, for three
  reasons that compound. The comparison there runs against the registry's own text rather than
  against a declaration, so the registry is one more uncoupled copy, which is the argument that
  keeps a proto comment from being a master. It can only fail in the direction where the far side
  moved: move the declaration and every needle goes on rendering the old digits, green. And when it
  does fail it names the wrong constant, which was measured, not argued: moving the compose
  publish's host-side interface, or the body app contract's `CORTEX_BRAIN_ADDR` default, fails
  **the brain's seam port**, a value neither of them spells. Worse, a shadow is not even evidence
  that the value is there. Of those two dozen `127.0.0.1`s exactly one is the brain's bind host;
  the rest are the body's own bind, the two `CORTEX_*_ADDR` client defaults, the publish's
  host-side interface and a handful of loopback dials, all of which go on saying `127.0.0.1` after
  the bind host moves. So the remedy for a shadowed value is to **register** it, never to read the
  shadow as coverage, and a new entry's needles carry only their own value where the shape allows:
  the RPC contract writes the host and the port on one line and the two entries pay it once each,
  from opposite ends.
- **The admission wait was sorted on those same two rulings** (ADR-0029 admission-wait addendum),
  which took an entry that did not exist to one site and four mentions. The entry's own account of
  the tree named two documents and the tree carries five far sides, one of them a code comment in
  the module that declares the deadline sitting under this bound. Held: the delegation runbook's
  env paragraph, the two module contracts (one restating the field, one the constant), and that
  ordering comment. Out on the derived-literal ruling: the four sentences saying the bound is twice
  1800 s and four times 900 s, which are consequences of the wait and of a measured batch, so a
  needle over one would fail when the measurement moved. Out on the rule that keeps decision
  records out: [index.md](../index.md)'s catalogue entry, which says what a dated addendum decided
  and stays true after the default moves. Out on the suite rule: the two unit tests asserting the
  default, which run on every commit.
- **The stall ceiling followed the admission wait** (ADR-0029 stall-ceiling addendum), taking the
  third number in that ordering sentence to one site and four mentions. Its entry named three far
  sides and the tree carries four, the miss being
  [brain-inference.md](brain-inference.md)'s "600 s for the CPU pool". The hoist landed in
  `config_subagents.py` beside `DEFAULT_MEM_BUDGET_GB` rather than in `cortex_core` beside the run
  deadline: the pure core never spends this number, and moving it there to suit a scan would put a
  constant in the core that nothing in the core reads. Out because it states no number: the compose
  override's knob list, which documents the env var and leaves the value to the brain. Out on the
  suite rule: the unit test asserting the default. The resident tier's `stall_timeout_s` is a
  different constant sharing the field name (120.0 in `config.py`) and ran as the control.
- **A defaults fault that names one place twice now points at the note behind it** (ADR-0026
  note-remedy addendum). `composedefaults.py` reads a note written after a value as a second spend
  of the variable it names, so a stale note is two spends that disagree, reported by naming one
  `path:line` twice and nothing else. `defaultcheck.one_line_hint` appends the remedy when a group
  repeats a place. The condition is a **repeated** place and not one the whole group shares, which
  the backlog entry had wrong: the planted note fails a group of five spends across four files.
  No `#` is looked for, since `"${V:-a}/in:${V:-b}"` is one value spending one variable twice, so
  the sentence names the shared line and offers the note as a likely reading.
- **And a copy the compiler can reach is an import, not a row**, which the registry's own suite
  enforces: `test_every_registered_constant_spans_more_than_one_language` refuses an entry whose
  places are all one suffix, on the ground that it proves nothing about a seam. The same headroom
  suite copied the body's `DEFAULT_MAX_EDGE` as a literal beside the brain's edge, and registering
  the pair failed that invariant, correctly. The suite already imports from the module declaring
  it, so the copy stopped being a copy. That puts the line between the two constants in that file
  at **reach** rather than importance: both are numbers the suite must follow rather than choose,
  one is declared where a compiler can hold it, and only the other has nothing but this scan. It is
  the same reason the brain's own unit test on the seam port stays out.
- **The prose around that same edge is the survey the import left** (ADR-0029 body-edge addendum),
  and it is the first sort where the number is spelled more often in fixtures than in claims.
  `DEFAULT_MAX_EDGE` is now one site and seventeen mentions across eleven files: its own two doc
  sentences, the headroom suite's two, `images.py`'s prose, `config_body.py`'s two,
  `test_config.py`'s comment, the body override's, the proto comment on `max_edge`, two module
  contracts and five runbook sentences. The tense test needed sharpening for a number quoted as
  often as it is measured at: a sentence naming this edge as **what the body answers with** is a
  far side, one naming it as the size a measurement was **taken at** is history. Out on that: the
  vision runbook's dated illegibility reading, the two byte readings at `1600x900`, and the shrink
  ladder's arithmetic. Out because a picture needs a size: the thirty one spellings in nine
  fixtures that build a 1600x900 frame. And out on the suite rule, which this sharpened too: a
  suite CI runs holds what it **asserts**, so `screen.rs` and `body_server.rs` pinning the default
  are out while `test_config.py`'s comment, which no assertion reaches and no Python can import,
  is in.
- **A host file is a live instruction, not a record**, which is the reading both sorts needed.
  `docs/host/` holds work that is built and unrun, its prerequisites exist so a sitting does not die
  on setup, and a completed item's file shrinks to a heading, its status and a pointer, so the
  sentence naming a value never survives into the record it would otherwise become. A stale number
  there costs a sitting, which is the failure that section exists to prevent.
- `bindcheck.py` does the same (`test_the_repo_itself_is_clean`), with a guard on the guard:
  `test_the_repo_really_declares_binds_for_this_gate_to_have_checked` fails if the reader ever
  finds fewer than six defaulted bind sources under `docker/`, so the clean verdict cannot go
  vacuously green on a reader that stopped matching.
- `defaultcheck.py` is held to that pattern twice over.
  `test_the_repo_itself_carries_one_default_per_variable` is the clean verdict;
  `test_the_repo_really_spells_variables_more_than_once` fails
  if the reader ever finds fewer than six variables with a sibling to disagree with; and
  `test_the_repo_really_spells_one_value_two_ways` pins the set of variables whose defaults differ
  in text at exactly `{CORTEX_SUBAGENTS_MEM_BUDGET_GB}`, which is the one pair the value comparison
  exists for. That last one is a set and not a membership on purpose: a SECOND re-spelling landing
  in the tree fails here and gets argued, rather than riding in on a comparison written for the
  first. The deliberate pair is pinned green in the suite and a real drift in the same variable
  pinned red beside it, because a gate that passes the pair by passing everything is no gate.
- `backloganchors.py` is held to both halves of that same pattern:
  `test_the_repo_itself_offers_every_anchor_aimed_at_it` runs the anchor check over the real
  tree, and `test_the_repo_really_aims_pointers_at_both_indexes_from_outside_the_backlog` fails
  if either index ever stops being pointed at from outside its own directory, the population a
  backlog-only scan would have missed being the one that guard exists to keep in the input.
  `test_the_repo_really_aims_pointers_at_documents_that_are_not_a_backlog_index` is the same guard
  over the half the scan later grew, so a widening that judged nothing new could not report green.
- `headingshapes.py` is held to the same pair.
  `test_the_repo_itself_writes_no_heading_this_rule_cannot_slug` measures the clean verdict over
  every markdown file rather than assuming it, which is what makes the refusal a house style and
  not a migration, and
  `test_the_repo_really_offers_the_two_shapes_this_rule_must_not_report` fails if the tree ever
  stops carrying a code-span heading or an intraword-underscore one, those being the two shapes a
  detector written slightly too wide would fail first.
- `samplecheck.py` is checked against the real tree by its own suite the way `crosscheck.py` and
  `stubcheck.py` are, so `check-scripts` catches a drift even when `check-samplecheck` is not the
  recipe that runs, and a second test holds the walk to having read something: a runbook tree that
  came back empty would make the first one vacuous. Its fixtures are miniatures of the three
  shapes the committed runbooks really carry, a bare fenced line, one behind compose's container
  label, and one commented out inside a shell block and wrapped over two lines, and a further test
  reads the runbooks themselves so a shape nobody writes any more cannot go on being tested
  against itself.
- `rostercheck.py` is held to the same pair, and the second half of it matters more here than
  anywhere: `test_the_repos_own_rosters_hold` runs the gate over the committed tree, and
  `test_the_repo_really_writes_a_roster_in_both_shapes` fails if the registry ever stops
  exercising both ways a roster can be written, since a bulleted rule nothing bulleted would be a
  rule that cannot fail. A third holds every registered boundary phrase to appearing exactly
  once in its own document, which is what turns a roster that quietly slid out of its passage into
  a failure of the registry rather than a silent shrinking of what is compared. This document is
  one of the two the gate reads, so a module added to `scripts/` and left unnamed above fails the
  gate that lives in it.
- `flagcheck.py` is held to that pattern from both ends, which its own set makes possible. Its
  mutations run against a **copy of the committed tree**, both placements of it, rather than a
  fixture, so a
  server that moves house leaves the suite failing instead of quietly checking a stack nobody
  runs, and `test_the_committed_tree_is_green_so_every_red_below_is_the_mutation` is what makes
  every red below it the edit. The test the gate exists for is
  `test_a_server_no_registry_names_is_held_the_day_its_override_is_written`, which ADDS a server
  in a file nothing has heard of and asserts every requirement fails: taking a flag off a known
  server was already catchable by naming that file, and this is the half that was not. Its twin on
  the other placement is `test_a_fourth_tier_for_a_second_pick_is_held_the_day_it_is_declared`,
  which adds a tier to the sidecar's own tuple with the setting that makes it one and the tail its
  author forgot. The naming rule's own is
  `test_a_hosted_tiers_artifact_spelled_another_way_is_reported_rather_than_dropped`, which
  respells the alias and asserts both halves of the fault: the tier leaves the set, and the scan
  says so instead of passing over the two servers left behind.
  `subagentservers.py`, `hostedtiers.py` and `composestarts.py` each carry the same
  guard on the guard, asserting respectively that the committed tree really starts the servers it
  ships, that the committed sidecar really declares the tier it hosts, and that every
  committed compose file is a shape the reader can read, since a reader agreeing with its own
  fixtures and with nothing real would leave the gate green over an empty set.
- The exclusion lists above are the single definition of "non-test source file" and
  "generated code" for the cap. Change them only with an ADR update.
- `dashcheck.py`, `commitlint.py`, and their tests spell the dashes as `\uXXXX` escapes
  rather than literals, so the gates pass the rule they enforce. A literal would make the
  gate flag itself.
- `ci_paths.py` runs under a plain `python3` on a GitHub runner **before** any `uv
  sync`: it must never grow a third-party import. Its `RULES` table and the rule list
  in ADR-0006 are the same normative list, so change them together.

**Dependencies.** Python stdlib; dev-only: pytest, pytest-cov, pyright, ruff.
