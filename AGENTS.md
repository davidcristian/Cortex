# Cortex engineering rules

Every agent and every person working in this repo follows these rules. A change that breaks one of them is **not
done**, even when it works. This file is the contract; the detail lives in `docs/`: the map is
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), the index [docs/index.md](docs/index.md), the decisions
`docs/adr/`.

## What this is

A personal assistant that runs on one machine: inference, memory and state stay local, and only tools reach
outside. A host-native Rust/Tauri **body** (hotkey, overlay, screen capture, audio, input) talks over gRPC to a
dockerized Python **brain** (llama.cpp inference, orchestration, memory, MCP tool servers). Three model tiers
share one 24 GB GPU: a resident 9 to 12B multimodal **cortex**, small 2 to 4B **subagents**, and a 31B **brain**
model loaded on demand, which requires unloading the other two.
[ADR-0001](docs/adr/ADR-0001-architecture.md) says why.

## The one hard rule

**State must survive a model swap.** Models are loaded and unloaded at any time, so every model instance is
stateless and disposable. No conversation state, task state, working memory or in-flight context may live inside
a model-server process or a model's KV cache. All of it lives in the external stores, Redis for hot state and
Postgres for durable data, behind the `SessionStore` and `MemoryStore` ports. A handoff writes the context to
the store, swaps models, reloads the target from the store, runs, writes the results back, and swaps back. Every
agent is a stateless function over the store. Interfaces are designed around this rule from the first day,
because adding it afterwards is a rewrite.

## Architecture rules

- **Hexagonal on both sides of the language boundary.** A pure core with no I/O, then ports (Python `Protocol`s,
  Rust traits), then thin adapters. The core never imports a backend, an SDK, a network client or an OS API.
  Adapters translate and hold no business logic.
- **Ports before adapters.** A new capability starts as a port, a contract test and a fake. The real adapter
  must pass the same contract test the fake passes.
- **Two languages, one boundary.** Brain: Python 3.12+ (`uv`, async first), dockerized. Body and overlay UI: one
  host-native Rust (stable) and Tauri process, never dockerized. Rust never runs inference or orchestration;
  Python never runs on the host.
- **That boundary is gRPC, written once in [proto/body.proto](proto/body.proto).** No in-process FFI, so no
  PyO3. Everything crossing between body and brain is declared there, and both the tonic code and the Python
  stubs are generated from it.
- **Two places hold the platform differences**, each a port with an adapter per platform: the OS backends (Rust
  traits, crates selected by `cfg(target_os)`, Windows implemented, macOS and Linux `unimplemented!()` stubs)
  and `InferenceBackend` (llama.cpp today, ADR-0005). Everything else stays portable: no hard-coded paths, no OS
  assumptions in the core, configuration from the environment only.
- **Orchestration is explicit typed code in the core**, with no agent framework that hides the control flow. New
  capabilities and patterns are welcome, and breadth is a goal, as long as each one is added behind a port,
  contract-tested and documented.

## What every change must pass

1. **At most 300 lines per non-test source file** (`.py`, `.rs`, `.ts` and `.tsx`, counting comments and blank
   lines) **and at most 250 lines per markdown file**, the two generated backlog indexes excepted. Anything
   longer fails. Split by responsibility as you write, never as a later cleanup: a document over the limit says
   two things, or contains measurements that belong in a readings record. Generated stubs and build output are
   exempt, and the overlay's stylesheet and markup and [proto/body.proto](proto/body.proto) are the only source
   files outside the limit.
2. **100% line and branch coverage in both toolchains.** Python: `pytest --cov` with branch coverage and
   `--cov-fail-under=100`. Rust: `cargo llvm-cov` with a failing 100% threshold. Tests assert behavior, use
   fakes rather than mocks, and cover error and edge paths; a test written only to reach a line is a violation.
   Generated code is left out of coverage, while hand-written wrappers around it are ordinary code. Use an
   escape hatch (`# pragma: no cover`, `#[cfg_attr(coverage, coverage(off))]`) only for code that can never run,
   such as a stub for another OS or a `__main__` guard, with the reason inline.
3. **Real GPU, OS and network calls live only in thin adapters.** Their live tests are marked `integration`,
   left out of the coverage requirement, and run by hand rather than in CI. **The agent counts as the host
   here:** the agent validates GPU and model behavior itself, through Docker against the real models, rather
   than handing that work to the maintainer. Only validation needing the real OS, the Windows Rust/Tauri body,
   is left to the host. **CI runs without a GPU** and builds all four toolchains: Python, Rust, the `body/app/`
   overlay and the Tauri shell. Each job runs when a change can affect it, and shared or unknown paths run all
   of them, so an unknown path fails safe (ADR-0006).
4. **Documentation is part of done.** Per slice: design doc or ADR, the port, tests, the implementation, the
   module doc and runbook updates, and finally **every deliberately deferred refinement written down in
   [docs/refinements/](docs/refinements/index.md), one file per task**
   ([ADR-0039](docs/adr/ADR-0039-backlog-per-task.md)). A change that touches code but not docs is unfinished,
   and a refinement postponed without a written record is a lost decision. A task's close is written in its own
   file's `## History`, and changes an ADR only when the decision that ADR states has changed. **A task's status
   is written on its `**Status:**` line and nowhere else**, and both backlog indexes are generated by `just
   backlog`, so never edit one by hand. [docs/host/](docs/host/index.md) has the same layout and holds work that
   is written but needs a real Win32 desktop session or a 24 GB GPU; anything the agent can reach belongs in
   neither and is done now. Every module also has a short contract doc in `docs/modules/` (purpose, public
   contract, invariants, dependencies).
5. **Types and quality.** Python: `ruff` (lint and format) clean, `pyright` in strict mode clean, no `Any`
   without a reason, public functions fully typed, explicit typed exceptions and never a bare `except`. Rust:
   `cargo fmt --check` clean, `cargo clippy -- -D warnings` clean, no `unwrap()` or `expect()` where the call
   can fail (`Result` plus `thiserror`), `unsafe` only with an ADR. Both: structured logging, no secrets in
   logs, **no secrets in the repo**, configuration from environment variables only.
6. **`just check` is the single command.** It runs ruff, pyright, pytest with coverage, `cargo fmt --check`,
   clippy, `cargo test`, `cargo llvm-cov`, the overlay's typecheck and Vitest coverage, and
   **the cross-tree scans**, thirteen of them:

   - `linecap.py`: the two line limits above.
   - `dashcheck.py`: no dash used as punctuation in any text file.
   - `prosecheck.py`: no banned word from the table below, and no docstring or comment block over three lines.
   - `crosscheck.py`: a value written in more than one place still agrees everywhere.
   - `bindcheck.py`: no compose bind mount can create an untracked directory in the repo.
   - `defaultcheck.py`: a variable named in several compose files has one default.
   - `volumecheck.py`: every volume an image declares is covered by a mount or a tmpfs.
   - `stubcheck.py`: the committed Rust stub contains every comment the proto has.
   - `samplecheck.py`: a log line a runbook shows matches the call that writes it.
   - `rostercheck.py`: a list of names a document keeps matches the set it describes.
   - `flagcheck.py`: every subagent server has the flags its tier requires.
   - `settingscheck.py`: every setting a brain module reads is in its compose service's environment.
   - `backlogcheck.py`: each index matches its task files, every link resolves, and no task file name has a banned word.

   Each of them runs unconditionally, in CI too, and this list is itself compared against the recipes that run
   them. Pre-commit runs the same command. Run it before calling anything done.

   **One recipe is deliberately outside it**: `check-shell`, clippy on the Tauri shell for the host target and
   for `x86_64-pc-windows-msvc`, where the shell's `cfg(windows)` items are type-checked. CI schedules it and
   `just check` does not, because it is the only check needing system libraries a clean dev box need not have.
   Nothing else may join it. A check whose *evidence* is out of reach, rather than its toolchain, is not a
   second exception: it records the far answer in the tree, checks that record, and recomputes it by hand.

## Prose

Write comments, docstrings, docs and commit messages in plain English that a new reader understands on the first
read. [ADR-0040](docs/adr/ADR-0040-prose-and-comment-style.md) gives the reasons.

- **Comments.** Code has no comments unless one is strictly necessary: why a workaround exists, a constraint
  that is not visible (an ordering, a spec or bug link, a measured number the code depends on), or a directive a
  tool reads (`# pragma: no cover` with its reason, `# noqa`, `# type: ignore`, `// SAFETY:`). Delete a comment
  that repeats the code, tells history ("was X, now Y"), cites an ADR for background, or explains what a better
  name would say. A comment is one or two lines, three at most.
- **Docstrings.** One line saying what the module, class or function does. Delete a docstring that only repeats
  the name. Test functions and test modules have none, because the test name says what it checks. Add a second
  or third line only when an argument or return value is not obvious from its name and type. Never more than
  three lines. Design reasons go in an ADR or a module doc, history in git.
- **Docs.** A markdown file is at most 250 lines, except the two generated backlog indexes, and `linecap.py`
  checks it. Write for a reader who has never seen this repo: say what a thing is and does, then why, when the
  why is not obvious. Keep facts, numbers, commands, file paths and decisions. Cut the story of how the code
  got here, repeated explanations (link to the one place instead) and hedging.
- **Plain words.** Short sentences, one idea each, subject first, with the literal verb: "checks", "fails",
  "returns", "stores", "sends", "is set to". Code does not know, notice, want, refuse, believe, agree, argue,
  answer, promise or own anything, so say what it does. Define a technical term once, where it first appears. No
  metaphors, idioms, wordplay or invented terms. The designed product names are exempt (body, brain, cortex, the
  mark's Mull, Muse, Hunch and Tangent, the window's Still, Lucid, Reverie and Trance, and the console's Face
  and Chords), and so is anything in backticks.
- **Measurements.** Write a figure that describes only the machine it was taken on as a ratio of that machine's
  own numbers, and name the fields an operator queries on their own hardware. Keep a figure absolute when a
  reader compares it with their own hardware to decide whether something fits, such as a memory budget or the
  size of a model.

**Banned words.** The words in the left column below may not appear in prose, in any capitalization, and a phrase is
found even when a line break splits it. `scripts/prosecheck.py` reads this table and reports every use in docs,
comments, docstrings and the strings `scripts/`, the brain, the body, the recipes, the shell scripts and the YAML
and TOML files print, show or raise, plus every docstring or comment block over three lines; `just check` runs it on
every change. `scripts/commitlint.py` reads the same table and refuses a commit message using one of these words
outside a paste. Backticks, link targets, URLs and a path or flag inside a string are not searched. The table is a
minimum: rewrite any other figurative word the same way.

| Do not write | Write instead |
| --- | --- |
| load-bearing | required, essential |
| gate, gates, gated, gating, ungated | check, checked, must pass, enforced by |
| pin, pins, pinned, pinning | fix, lock, set exactly, assert |
| spell, spells, spelled, spelling, spellings, respell | write, name, define, form |
| carry, carries, carried, carrying | contain, include, have, keep, pass |
| land, lands, landed, landing | commit, merge, add, end up |
| seam, seams | boundary, interface (the `seam` package in backticks is fine) |
| arm, arms, armed, arming | variant, condition, branch, set, enable |
| sitting, sittings | run, measurement session |
| sweep, sweeps | review, pass |
| heal, heals, healed, healing | fix, repair |
| bite, bites | name the event that makes it matter |
| ride, rides, riding | is sent with, goes with |
| standing | current, permanent, ongoing |
| in force | current, in effect |
| needle, needles | search text |
| knob, knobs | setting |
| lever, levers | setting, option |
| honest, honestly | accurate, correct, real |
| verdict, verdicts | result |
| re-derive, re-derives, re-derived, re-deriving, rederive | recompute, check again |
| earn, earns, earned | say why it is justified |
| backstop, tripwire, ratchet, footgun, chokepoint | describe the mechanism |
| robust, seamless, seamlessly, comprehensive, crucial, crucially, critically, fundamentally | state the specific fact |
| leverage, leverages, delve, utilize, worth noting | use, look at, (state the fact) |
| under the hood, boils down, low-hanging, rabbit hole, north star, belt and braces, silver bullet | say it literally |

## Commits

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), enforced by two commit-msg hooks:
conventional-pre-commit for the type and format, `scripts/commitlint.py` for the rest of the style. Imperative
mood is the one convention no machine checks.

- **The subject says what changed; the body says why it was needed.** A subject starts with a verb of change
  (`add`, `fix`, `remove`, `split`, `rename`, `reject`, `document`), names what changed, and reads correctly to
  someone who has not seen the diff, rather than describing a relation between two files as though the relation
  were the action. The body states the problem, then what the change does about it.
- **The body is at most 50 words**, which `scripts/commitlint.py` counts: two or three plain sentences, the
  problem first and then what the change does about it. Write no body at all when the subject says everything.
  Text inside a code fence is not counted, so a mutation table keeps its rows. Reasoning belongs in `docs/`,
  and a message needing it points there.
- Format: `type(scope)?: subject`, imperative mood, lowercase subject, no trailing period, subject at most 72
  characters. The body wraps at 72, which `scripts/commitlint.py` checks: a line past 72 that could have been
  wrapped fails, while one whose longest word alone is over the wrap (a URL, a path, a long identifier) has
  nowhere to break and is exempt. Two more kinds are exempt for what they are, since rewrapping a paste changes
  what it says: a line inside a code fence, and one whose first token is a bare `$` prompt. That is how a
  message declares a paste, and a paste is exempt from this rule, the word count above and the dash rule below,
  from nothing else. An unclosed fence is reported; a `BREAKING CHANGE:` footer is neither, so it wraps.
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `revert`. A breaking change
  adds `!` after the type or scope plus a `BREAKING CHANGE:` footer. Scopes are optional and used only when the
  change stays inside one area: `brain`, `body`, `scripts`, `proto`, `docs`, `ci`. Never repeat the type as its
  own scope (`docs(docs)`).
- **Self-contained: no volatile references.** A message must still read correctly once the planning docs move
  on, so never cite a slice number, an ADR number, a roadmap entry, an audit, a commit hash, or any numbered
  pointer into a document that changes (`check 3`, `assumption 1`, `§5`). Name the capability, the decision or
  the behavior instead. Code paths, package names, env vars and measurements are stable and stay welcome. A
  paste is **not** exempt: a pasted hash stops resolving on the same rewrite a cited one does.
- **No banned word and no dash as punctuation.** The table above applies to a commit message too, and
  `scripts/commitlint.py` checks both rules. No em dash, en dash or spaced `--` in a subject or body:
  restructure the sentence rather than swapping in another mark. Hyphenated words and CLI flags (`--locked`)
  are unaffected, and so is any line inside a paste, whose text the author did not write.
- One logical change per commit. Every commit passes `just check`, which the pre-commit hook enforces.

## Working agreement

- **Vertical slices, not horizontal layers.** Each increment is a thin end-to-end path: small, green and
  documented. No scaffolding of empty layers.
- **Scope grows freely; design stays extensible.** More capability is welcome and feature creep is not a worry,
  but every addition is built for extension: behind a port, contract-tested, swappable, documented. When a
  design is hard, design the interface rather than cutting scope to avoid it.
- **Decisions are written down.** Any non-obvious choice becomes an ADR in `docs/adr/`. If a requirement is
  underspecified, record your reading of it as an ADR and continue rather than waiting, and name the riskiest
  assumptions in your summary. An ADR states the decision that applies today, in at most 250 lines, and is
  edited in place when that decision changes; git keeps the older versions, so nothing is appended to one. The
  measurements it rests on live in `docs/readings/<subject>.md`. Both formats are described in
  [docs/adr/README.md](docs/adr/README.md) and [docs/readings/README.md](docs/readings/README.md).
- **Names are designed, never defaulted.** Anything pickable or family-shaped (a registry of styles, themes,
  modes) gets a naming scheme built with the same care as its visuals: one word per entry, one metaphor per
  family, and the family's structure meaning something. Sibling families use related vocabularies: the mark's
  labels are movements of thought (Mull, Muse, Hunch, Tangent) and the window's are depths of sleep (Still,
  Lucid, Reverie, Trance). No collisions with an existing family or token. Propose a recommended set with real
  alternatives before choosing one. A storage key freezes once anything beyond this machine depends on it, so
  name it right on day one. The worked example is decision 7 of [ADR-0031](docs/adr/ADR-0031-bubble-mark.md).
- **Claims come with evidence.** Never report a check as green without having run it in this session; show the
  command and its output. Label an unverified statement as an assumption.
- **Prove a check can fail.** A check that cannot fail is a defect: after writing or changing one, break the
  thing it checks and watch it fail before trusting it. A mutation table is that proof written down, and **it
  goes in the body of the commit that makes the change**, inside a code fence so the body's width rule leaves
  its columns alone, rather than in an ADR, a readings record or a runbook, because the replay pass reads commit
  bodies. **It names the test suite its counts are over**, since the diff shows the file and the edit but
  nothing about the collection a number counts. No machine checks either rule, for the same reason none checks
  imperative mood. See [docs/readings/mutation-replay.md](docs/readings/mutation-replay.md) and
  [ADR-0002](docs/adr/ADR-0002-toolchain-checks.md#mutation-tables-and-the-replay-pass).
- **Read before you write.** Open the file and its call sites before editing; never edit from memory of its
  contents, and never invent an API. Check the signature.
- **Report faithfully.** Report a failing test with its output and name every step you skipped. Report a task as
  done only when it is: an inaccurate "done" costs more to undo than an accurate "not yet" costs.
- **Stop when surprised.** When output contradicts your model of the system, work it out again from the
  evidence. Do not match it to the nearest familiar failure and push through.
- Keep this file and all docs short and full of pointers; context bloat is a defect.
