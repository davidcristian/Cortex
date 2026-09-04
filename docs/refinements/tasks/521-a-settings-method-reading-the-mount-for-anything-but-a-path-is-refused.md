# A settings method reading the mount for anything but a path is refused

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a `ModelHostConfig` method other than `_path` needs `models_root` for something that
is not an artifact path, reporting the mount on `GET /health` or checking that it exists at
startup, which nothing in the sidecar does today. That is countable by reading every method of
`ModelHostConfig` and asking which of them name `self.models_root`
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of
[R-515](515-the-artifact-domain-rests-on-a-field-name-convention.md), which made
`scripts/artifactnames.py` find a hosted artifact by the resolver the sidecar hands it to and
refuse a read of the mount root anywhere else.

`artifactnames.resolved` raises on any method of `ModelHostConfig` other than `_path` that reads
`self.models_root`, naming the method and the remedy. The refusal exists for one shape: a path
joined onto the mount by hand, `f"{self.models_root}/{self.brain_file}"` in `tiers()`, which is a
second resolver the reader does not read and an artifact it would miss in silence. The refusal is
wider than that shape. A method that reads the root to report it, to check the directory exists, or
to log it at startup joins nothing onto it and names no artifact, and is refused with the same
message, whose remedy (join a path onto the mount in `_path` only) does not fit a read that joins
nothing. Nothing in `config.py` reads the mount outside `_path` today, so the wider refusal costs
nothing yet and the originating close flagged it as the one taste risk of the reading.

**What would close it.** Narrow the refusal to a read that joins the root onto another value: an
f-string or a concatenation that carries `self.models_root` beside something else, or a call
handed it together with a field. A bare read, the root passed whole to a log line or a check, would
pass. The narrowing needs its own test for the shape it now lets through, and the message should
say which shape was refused. The alternative, a second named accessor the reader is taught, adds a
constant for a method nothing needs, and is the weaker answer until a real second reader asks for
it.

## Trail

- 2026-09-02: opened by the close of
  [R-515](515-the-artifact-domain-rests-on-a-field-name-convention.md), recorded in the [ADR-0029
  addendum on the artifact domain being the
  resolver](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-09-02-the-artifact-domain-is-the-resolver-and-the-compose-flag-set-widens),
  under the refusal that names this as its taste risk.
- 2026-09-04: checked and left open. The trigger has not fired. `ModelHostConfig` declares six
  methods, `tiers`, `roster`, `_vision`, `_reasoning`, `_image_budget` and `_path`, and reading
  each for `self.models_root` finds it in `_path` alone, on the one line that joins a file onto the
  mount. `tiers` no longer carries the hand-joined path this refusal was written for, so the
  refusal has nothing to report and nothing to over-report either. `artifactnames.resolved` returns
  four fields today, `cortex_file`, `brain_file`, `subagent_gpu_file` and `cortex_mmproj_file`,
  each found by the resolver call it is handed to rather than by its name, so narrowing the refusal
  would change no answer the reader gives now.
