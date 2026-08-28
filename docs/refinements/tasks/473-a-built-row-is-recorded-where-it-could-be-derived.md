# A built row is recorded where it could be derived

**Status:** open, actionable
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
