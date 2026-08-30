# A third family that appends nothing either way still reads as open

**Status:** open, actionable
**Area:** inference
**Trigger:** a pick entering the lineup whose template renders one identical tail with the thinking
key and without it, and closes its thought in a spelling `scripts/switchtail.py` does not list.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-30 by the close of
[R-509](509-a-third-familys-closed-thought-reads-as-an-open-one.md), which gave the rendering
reader a third state and drew its line with the one comparison it already had.

`switchtail.py` now refuses to read a switched tail that carries no marker of either family it
knows **and** differs from the tail the same template renders with the key left alone. The second
half of that test is what makes the first half safe: the failing pick answers the key by dropping a
`<|think|>` system turn at the front, so its tail is byte identical both ways, and refusing every
unmarked tail would refuse the one pick the module exists to read correctly.

The case the discriminator cannot see is the other one. A template that renders **one identical
tail** both ways and closes its thought in an unlisted spelling falls on the failing pick's side of
the line and is read as an open door, which is the same wrong verdict this entry's parent was
about, one case narrower. It is not unguarded: a tail that closes the thought invites no
deliberation, so that tier's control arm, the same request with no switch, would fail to deliberate
on every draw and the run refuses one step later for that. The operator sees "this prompt invites
no thought here and the switch stopped nothing" where the true reading is "this reader does not
know your template", which is a red in the wrong words rather than a verdict published off a guess.

**Why it was left.** Naming that case needs something the tail cannot supply, since by construction
the key changed nothing after the ask: it needs either a third family's spelling in the vocabulary,
which is a lineup decision with a person looking at it, or a reading of the control arm's own
rendering against its cell, which is a second rule about a tier this module can say nothing else
about. Both want a real template to be measured against, and the deferral is now genuine in a way
the parent entry's was not: there the missing input was already in hand.

**What would close it.** Either a third pair in `MARKERS` once a pick that needs one is picked,
which makes this case ordinary, or a sentence in the control-arm refusal naming the possibility
that the control did not fire because the template closed the thought in a spelling this reader
cannot see. The second is cheap and is a hint rather than a verdict; the first is the honest fix
and needs the pick.

## Trail

- 2026-08-30: opened by the close of
  [R-509](509-a-third-familys-closed-thought-reads-as-an-open-one.md), recorded as the ADR-0005
  third-spelling addendum.
