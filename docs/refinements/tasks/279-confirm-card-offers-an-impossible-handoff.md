# The confirm card offers a handoff the machine cannot run

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** a user asking why they were asked to approve a deep task that then did not happen, or a deployment configuring escalation without a deep artifact for long enough that the card becomes a nuisance.

Opened 2026-08-16 by the close that refuses an impossible handoff before the drain
([R-203](203-escalation-fault-not-remembered.md)), which moved the refusal from after the stall to
before it and left one surface still lying: the ADR-0022 confirm card.

On a deployment whose model host carries no deep tier, the cortex still advertises
`escalate_to_brain`, still calls it, and the user is still shown a card saying the deep model will
take over and the machine will be busy for a while. They approve it, and the conductor then refuses
with the honest note. Nothing is unloaded and nothing is lost, so what remains is a question asked
under a false premise.

**Both surfaces that could close it are the per-turn hot path, which is why this waits.** The tool
spec is rebuilt per turn (`build_cortex_tools`), and the gate's reason is static config
(`DispatchPolicy.gate_reasons`), so keeping either truthful means asking the model host whether it
carries the tier on every turn, for a fact that changes only when a container restarts. The
tier-sweep close already refused a per-turn control call for exactly this kind of fact, and the
loop that does pay for readings on an interval (`TierHealer` over `sweep_tiers`) deliberately does
not look at the deep tier at all, because the deep tier has its own verdict at the swap.

So the shape a fix would take is a reading somebody already pays for, not a new one: either the
sweep grows the deep tier as a tier it observes for advertisement purposes only, which reopens the
question the tier-sweep close settled about what that record is for, or the wrapper caches the
conductor's own answer for the turn that follows it, which is a cache with the same invalidation
problem the close argued its way out of. Neither is obviously right, and both cost more than the
one confirm card they save.
