# A built row is recorded where it could be derived

**Status:** done 2026-08-29
**Area:** repo-checks
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)

`scripts/imagevolumes.py` has ten rows. Seven are pulled references, which only a registry can
answer for, and that is what the recorded answer exists for. The other three are `cortex-brain`,
`cortex-mcp-email` and `cortex-model-host`, and since the base rows were added, what each declares
looked computable: the union of what its Dockerfile declares, which `dockerfilevolumes.py` reads,
and what its base's row contains, which `dockerfilebases.py` resolves. The rule over the built rows
is one-directional, so a built row declaring more than its two sources is not a failure and one
declaring less is.

Deriving the rows instead would rest on a completeness claim measured once, on one host: that a
built image's `Config.Volumes` is exactly the union of its base's and its own `VOLUME`
instructions. It would also remove the two-directional comparison `just image-volumes` makes
against a real daemon, which is an independent reading.

## History

- 2026-08-28: opened by the close of
  [R-443](443-a-built-rows-answer-comes-from-whatever-this-machine-last-built.md), which recorded a
  row for each base the built rows stand on.
- 2026-08-29: closed as [ADR-0067 decision 10](../../adr/ADR-0067-image-volume-record.md), decided
  recorded, because the completeness claim was measured and is false. A base whose only instruction
  is `ONBUILD VOLUME /probe/onbuild` declares no volume of its own, so its row would be the empty
  tuple both real bases have, and an image built `FROM` it by a Dockerfile with no `VOLUME`
  instruction declares `/probe/onbuild` (docker 29.7.2, under BuildKit and under
  `DOCKER_BUILDKIT=0`). The union of the two readable sources is a lower bound on what a built image
  declares and never an upper one, so a derived row would report a clean pass on an image whose
  every container takes an anonymous volume. The three inherited readings held: a declaration is
  inherited through `FROM`, a union with a path on each side merges, a builder stage's reaches no
  built image, and `VOLUME []` fails the build rather than removing a declaration. The record and
  the derivation stay two independent readings of one image. The close also upgraded both
  one-directional rules from a cost concession to a correctness requirement, and retired the
  sentence claiming the union is the whole of what a built image declares from the
  `volumecheck.py` docstring, the `check-volumecheck` comment in the justfile and
  [docs/modules/repo-checks.md](../../modules/repo-checks.md). No rule changed, so no mutation
  table; `just image-volumes` against a real daemon agreed with all ten rows the same day. Opened by
  this close: [R-493](493-a-base-may-declare-a-volume-through-onbuild.md).
