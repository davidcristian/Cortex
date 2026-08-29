# A built row is recorded where it could be derived

**Status:** landed 2026-08-29
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Opened 2026-08-28 by the close of
[R-443](443-a-built-rows-answer-comes-from-whatever-this-machine-last-built.md), which recorded a
row for each base the built rows stand on and, in doing so, made the built rows computable.

`scripts/imagevolumes.py` holds ten rows. Seven are pulled references, which only a registry can
answer for, and that is what the whole recorded-answer arrangement exists for. The other three are
`cortex-brain`, `cortex-mcp-email` and `cortex-model-host`, and since the base rows landed, what
each of those declares is no longer a fact only docker knows: it is the union of what its
Dockerfile declares, which `dockerfilevolumes.py` reads, and what its base's row carries, which
`dockerfilebases.py` resolves. Both halves were measured to be the whole (a declaration is
inherited through `FROM`, and a builder stage's reaches no built image), and the gate already reads
both on every commit.

So the three built rows are a recorded measurement of something the tree can compute. Today the
rule over them is one-directional, which is what keeps that harmless: a built row carrying more
than its two sources declare is nobody's fault, and a built row carrying less is a red. Deriving
the row instead would mean the record held only what a registry can answer for, `just
image-volumes` had nothing to ask about a built image at all, and the last reason a built row can
be wrong went away rather than being held.

**Why it was left.** The close it came out of was about making the base visible, and this is about
what that makes redundant. It also rests on a completeness claim that was measured once, on one
host, on one docker: that a built image's `Config.Volumes` is exactly the union of its base's and
its own `VOLUME` instructions, with no other instruction and no builder flag able to add or remove
one. That claim is load-bearing in a way it is not today, since today it only has to be true in one
direction. Removing rows also removes the two-directional record check over them, and a row nobody
records is a row the `--rederive` half stops comparing, which is a real loss of an independent
reading even where the derivation is right.

**What would close it.** Decide whether the three built rows are derived or recorded, and say why
on the record. If derived, the completeness claim needs measuring rather than assuming, over both
Dockerfiles here and at least one image carrying a `VOLUME` on each side of the union, and the
`--rederive` half needs to say what it now does about an image it no longer asks about: comparing
the derivation against a real built image is the obvious answer and is a stronger check than the
row it replaces. If recorded, say so on `imagevolumes.py` beside the paragraph that now explains
why the bases have rows, since a reader who follows that reasoning one step further arrives here.

## Trail

- 2026-08-28: opened by the close of
  [R-443](443-a-built-rows-answer-comes-from-whatever-this-machine-last-built.md).
- 2026-08-29: **landed** as the [ADR-0011 addendum on why the built rows stay
  recorded](../../adr/ADR-0011-body-v1.md), decided **recorded**, because the completeness claim
  this entry asked to have measured was measured and **is false**. A base whose only instruction is
  `ONBUILD VOLUME /probe/onbuild` declares no volume of its own, so the row for it would be the
  empty tuple both real bases carry, and an image built `FROM` it by a Dockerfile with no `VOLUME`
  instruction declares `/probe/onbuild` (docker 29.7.2, under BuildKit and under
  `DOCKER_BUILDKIT=0`). The union of the two readable sources is a floor under what a built image
  declares and never a ceiling, so a derived row would report a clean pass on an image whose every
  container takes an anonymous volume, which is the leak the gate exists to catch arriving through
  it rather than past it. The three readings the entry inherited held on re-derivation: a
  declaration is inherited through `FROM`, a union with a path on each side merges, a builder
  stage's reaches no built image, and `VOLUME []` is refused rather than un-declaring. The record
  and the derivation therefore stay two independent readings of one image, and the entry's
  suggested replacement is not stronger: it is the same single reading with the tree's side
  computed from a claim now known false. The reading also upgrades both one-directional rules from
  a cheapness concession to a correctness requirement, since a built row is supposed to be able to
  carry more than the tree can read, and it retired the "whole of what a built image declares"
  sentence in three places that asserted it in the present tense, the `volumecheck.py` docstring,
  the `check-volumecheck` comment in the justfile and
  [docs/modules/repo-gates.md](../../modules/repo-gates.md). `imagevolumes.py` now answers the
  question beside the paragraph that raises it. No rule changed, so no mutation table; the evidence
  is the measurement, and `just image-volumes` against a real daemon agreed with all ten rows the
  same day. Opened by this close:
  [R-493](493-a-base-may-declare-a-volume-through-onbuild.md), the third source itself, which no
  gate here can see until a rebuild.
