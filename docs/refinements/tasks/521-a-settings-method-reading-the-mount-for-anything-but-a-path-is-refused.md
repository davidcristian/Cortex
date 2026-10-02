# A settings method reading the mount for anything but a path is refused

**Status:** declined 2026-10-02
**Area:** repo-checks
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)

`artifactnames.resolved` raises on any method of `ModelHostConfig` other than `_path` that reads
`self.models_root`, naming the method and what to do. The refusal exists for one shape: a path
joined onto the mount by hand, `f"{self.models_root}/{self.brain_file}"` in `tiers()`, which is a
second resolver the reader does not read and an artifact it would miss without reporting anything.
The refusal is wider than that shape. A method that reads the root to report it, to check the
directory exists, or to log it at startup joins nothing onto it and names no artifact, and is
refused with the same message, which offers two remedies: joining a path onto the mount in `_path`
only, which does not fit a read that joins nothing, and teaching `artifactnames.py` the shape.

Closing it means narrowing the refusal to a read that joins the root onto another value: an f-string
or a concatenation that contains `self.models_root` beside something else, or a call handed it
together with a field. A bare read would pass. The narrowing needs its own test for the shape it
lets through, and the message should say which shape was refused.

## History

- 2026-09-02: opened by the close of
  [R-515](515-the-artifact-domain-rests-on-a-field-name-convention.md), recorded in the artifact
  naming decision of [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md), under the refusal that
  names this as its one risk.
- 2026-09-04: checked and left open. `ModelHostConfig` declares six methods, `tiers`, `roster`,
  `_vision`, `_reasoning`, `_image_budget` and `_path`, and reading each for `self.models_root`
  finds it in `_path` alone, on the one line that joins a file onto the mount. `tiers` no longer has
  the hand-joined path this refusal was written for. `artifactnames.resolved` returns four fields
  today, `cortex_file`, `brain_file`, `subagent_gpu_file` and `cortex_mmproj_file`, each found by
  the resolver call it is handed to rather than by its name, so narrowing the refusal would change
  no answer.
- 2026-09-14: read again and nothing moved. The same six methods, `self.models_root` in `_path`
  alone, and the same four fields from `artifactnames.resolved`.
- 2026-09-15: read again and nothing moved. The only other places the field is written are its own
  declaration and a comment saying what the check refuses.
- 2026-09-19: read again after the settings scan was added, since that scan reads `ModelHostConfig`
  too, and nothing moved. The settings scan reads the class's fields and not its methods, and it
  exempts `CORTEX_MODELHOST_MODELS_ROOT` with the reason that the gpu overlay mounts the models at
  `/models`, the default the field names; that is a read of the field's declaration, not a method
  reading `self.models_root`. The account of the refusal's message was short: it has offered a
  second remedy since it was added, and the paragraph above now quotes both.
- 2026-10-02: declined. The trigger has not fired: `ModelHostConfig` now has five methods,
  `tiers`, `roster`, `_vision`, `_reasoning` and `_path`, the image budget having become the module
  function `image_budget_flags`, and `self.models_root` is read in `_path` alone, which now resolves
  five fields, the deep tier's drafter `brain_draft_file` among them. The remedy is wrong. Written
  as stated on a scratch reader, a refusal of joins alone refuses an f-string join and an
  `os.path.join`, and passes a local alias (`root = self.models_root`, then
  `f"{root}/{self.brain_file}"`), `Path(self.models_root) / self.brain_file`, and a method returning
  the root for another method to join onto, which is the reporting case this entry wanted to let
  through. Each is the silent second resolver the refusal exists for. And the refusal costs neither
  case the trigger names: `server.py` already builds the daemon from `config.<field>` reads, so a
  mount reported on `GET /health` or checked at startup is written there, and a `field_validator`
  on `models_root` receives the value rather than `self` and is not refused either. That the reader
  does not look outside `config.py` is a gap of its own, filed as
  [R-774](774-a-second-model-host-module-joining-a-file-onto-the-mount-is-not-read.md). The
  refusal stays as wide as any read, and [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)
  decision 4 now says why.
